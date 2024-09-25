import argparse
from nornir import InitNornir
from nornir_netmiko import netmiko_send_command
from nornir_utils.plugins.functions import print_result
import re
import os
import datetime
from collections import defaultdict
from nornir import InitNornir
from nornir_netmiko import netmiko_send_command
from nornir_utils.plugins.functions import print_result
import re
import os
import datetime
from collections import defaultdict


def find_matching_template(description, parsed_templates):
    if not description:
        return None
    
    # Exakte Übereinstimmung
    if description + '.txt' in parsed_templates:
        return parsed_templates[description + '.txt']
    
    # Teilübereinstimmung
    for template_name, template_content in parsed_templates.items():
        template_base = template_name.rsplit('.', 1)[0]  # Entfernt die .txt Endung
        if template_base in description:
            return template_content
    
    return None

def generate_missing_config_files(results):
    config_dir = "missing_configs"
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    for host, result in results.items():
        if not result.failed:
            missing_config = []
            current_interface = None
            skip_mode = False
            
            for line in result.result.split('\n'):
                if "Skipped Interfaces" in line:
                    skip_mode = True
                    continue
                
                if not skip_mode:
                    if line.startswith("GigabitEthernet"):
                        current_interface = line.strip(':')
                        missing_config.append(f"interface {current_interface}")
                    elif line.startswith("Missing commands:"):
                        commands = line.split(":", 1)[1].strip().split(", ")
                        missing_config.extend([f" {cmd}" for cmd in commands])
                        missing_config.append("!")
            
            if missing_config:
                filename = os.path.join(config_dir, f"{host}_missing_config.txt")
                with open(filename, 'w') as f:
                    f.write("\n".join(missing_config))
    
    return config_dir


def generate_report(results, parsed_files, config_dir):
    now = datetime.datetime.now()
    report_filename = f"compliance_report_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_filename, 'w') as report_file:
        report_file.write(f"Compliance Report - Generated on {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_file.write("="*50 + "\n\n")
        
        report_file.write("Parsed Template Files:\n")
        for filename in parsed_files.keys():
            report_file.write(f"- {filename}\n")
        report_file.write("\n")
        
        report_file.write(f"Missing configuration files are stored in: {config_dir}\n\n")
        
        for host, result in results.items():
            report_file.write(f"Host: {host}\n")
            report_file.write("-"*20 + "\n")
            if result.failed:
                report_file.write(f"Task failed: {result}\n")
            else:
                # Gruppieren der Ports nach fehlenden Befehlen
                port_groups = defaultdict(list)
                skipped_ports = []
                current_port = None
                current_description = None
                
                for line in result.result.split('\n'):
                    if line.startswith("GigabitEthernet"):
                        current_port = line.strip(':')
                    elif line.startswith("Description:"):
                        current_description = line.split(":", 1)[1].strip()
                    elif line.startswith("Missing commands:"):
                        missing_commands = line
                        port_groups[missing_commands].append((current_port, current_description))
                    elif "Skipped Interfaces" in line:
                        skipped_ports = [p.strip() for p in result.result.split("Skipped Interfaces")[1].split('\n') if p.strip()]
                
                # Ausgabe der gruppierten Ports
                for missing_commands, ports in port_groups.items():
                    report_file.write(f"{missing_commands}\n")
                    report_file.write("Affected ports:\n")
                    for port, description in ports:
                        report_file.write(f"- {port} {description}\n")
                    report_file.write("\n")
                
                # Ausgabe der übersprungenen Ports
                if skipped_ports:
                    report_file.write("Skipped Interfaces (no matching template):\n")
                    for port in skipped_ports:
                        report_file.write(f"- {port}\n")
                    report_file.write("\n")
                
                report_file.write(f"See {host}_missing_config.txt for detailed missing configuration.\n")
            
            report_file.write("\n")
        
        report_file.write("="*50 + "\n")
        report_file.write("End of Report")
    
    return report_filename


def parse_intf_template_files_individually(directory_path):
    result = {}
    errors = []

    try:
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt'):
                file_path = os.path.join(directory_path, filename)
                try:
                    with open(file_path, 'r') as file:
                        required = []
                        additional_allowed = []
                        for line in file:
                            line = line.strip()
                            if line.startswith('#'):
                                continue  # Ignoriere Kommentarzeilen
                            elif line.startswith('+'):
                                additional_allowed.append(line[1:].strip())
                            elif line:
                                required.append(line)
                        
                        result[filename] = {
                            "required": required,
                            "additional_allowed": additional_allowed
                        }
                except IOError:
                    errors.append(f"Fehler beim Lesen der Datei {filename}")

    except FileNotFoundError:
        errors.append(f"Das Verzeichnis {directory_path} wurde nicht gefunden.")
    except PermissionError:
        errors.append(f"Keine Berechtigung, auf das Verzeichnis {directory_path} zuzugreifen.")

    return result, errors


def parse_interfaces(config):
    interfaces = {}
    current_interface = None
    
    for line in config.splitlines():
        line = line.strip()
        if line.lower().startswith('interface'):
            current_interface = line.split()[1]
            interfaces[current_interface] = {
                'config': [],
                'description': None
            }
        elif current_interface and line and not line.startswith('!'):
            if line.lower().startswith('description'):
                interfaces[current_interface]['description'] = line[11:].strip()
            else:
                interfaces[current_interface]['config'].append(line)
        elif line.startswith('!'):
            current_interface = None
    
    return interfaces

def check_interface_compliance(config, required_commands, additional_allowed_commands=None):
    if additional_allowed_commands is None:
        additional_allowed_commands = []
    
    allowed_commands = required_commands + additional_allowed_commands
    
    config_lines = config.split('\n')
    found_commands = set()
    unexpected_commands = []

    for line in config_lines:
        line = line.strip()
        if not line or line.startswith('interface'):
            continue
        
        if line in required_commands:
            found_commands.add(line)
        elif not any(line.startswith(allowed) for allowed in allowed_commands):
            unexpected_commands.append(line)
    
    missing_commands = set(required_commands) - found_commands

    if not missing_commands and not unexpected_commands:
        return "Compliant"
    else:
        result = "Non-Compliant.\n"
        if missing_commands:
            result += f"Missing commands: {', '.join(missing_commands)}\n"
        if unexpected_commands:
            result += f"Unexpected commands: {', '.join(unexpected_commands)}"
        return result.strip()

def check_switch_compliance(task, parsed_templates):
    host=str(task.host)
    print(f"Processing: {host}")

    result = task.run(netmiko_send_command, command_string="show running-config")
    config = result[0].result

    interfaces = parse_interfaces(config)

    non_compliant_interfaces = {}
    skipped_interfaces = []

    for interface, intf_details in interfaces.items():
        if re.match(r'^GigabitEthernet', interface, re.IGNORECASE):
            description = intf_details['description']
            matching_template = find_matching_template(description, parsed_templates)
            
            if matching_template:
                required = matching_template['required']
                additional_allowed = matching_template['additional_allowed']

                config_str = "\n".join(intf_details['config'])
                compliance_result = check_interface_compliance(config_str, required, additional_allowed)
                if compliance_result != "Compliant":
                    non_compliant_interfaces[interface] = {
                        'compliance': compliance_result,
                        'description': description
                    }
            else:
                skipped_interfaces.append(interface)

    if not non_compliant_interfaces and not skipped_interfaces:
        return "All checked interfaces are compliant"
    else:
        result = ""
        if non_compliant_interfaces:
            result += "Non-Compliant Interfaces:\n"
            for interface, details in non_compliant_interfaces.items():
                result += f"{interface}:\n"
                if details['description']:
                    result += f"Description: {details['description']}\n"
                result += f"{details['compliance']}\n\n"
        
        if skipped_interfaces:
            result += "Skipped Interfaces (no matching template):\n"
            for interface in skipped_interfaces:
                result += f"{interface}\n"
        
        return result.strip()


# Main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Interface Compliance Checker")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the Nornir config file (default: config.yaml)")
    parser.add_argument("-t", "--templates", default="interface_templates", help="Path to the interface templates directory (default: interface_templates)")
    parser.add_argument("-f", "--filter", help="Optional filter string for hostname prefix")
    parser.add_argument("-o", "--output", default=".", help="Directory to store output files (default: current directory)")
    args = parser.parse_args()

    # Einlesen der Template-Dateien
    parsed_files, errors = parse_intf_template_files_individually(args.templates)

    if errors:
        print("\nAufgetretene Fehler beim Einlesen der Templates:")
        for error in errors:
            print(error)

    # Initialize Nornir
    nr = InitNornir(config_file=args.config)
    
    # Anwenden des Filters nur wenn angegeben
    if args.filter:
        nr = nr.filter(lambda h: h.name.startswith(args.filter))
    
    print("Hosts in inventory:")
    for host in nr.inventory.hosts:
        print(f"- {host}")

    # Run the task
    results = nr.run(task=check_switch_compliance, parsed_templates=parsed_files)

    # Generate missing config files
    config_dir = os.path.join(args.output, "missing_configs")
    config_dir = generate_missing_config_files(results)

    # Print the results
    failed_hosts = []
    for host, result in results.items():
        if result.failed:
            print(f"Task failed on host {host}: {result}")
            failed_hosts.append(host)
        else:
            print(f"\nResults for host {host}:")
            print(result.result)

    if failed_hosts:
        print("\nThe Task failed on the following Hosts:")
        print('--------------------------------------------')
        for host in failed_hosts:
            print(host)
    else:
        print("\nTask completed successfully on all hosts.")

    # Generate and save the report
    report_file = generate_report(results, parsed_files, config_dir)
    report_path = os.path.join(args.output, report_file)
    print(f"\nDetailed report saved to: {report_path}")
    print(f"Missing configuration files are stored in: {config_dir}")
