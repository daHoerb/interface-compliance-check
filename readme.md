Network Interface Compliance Checker
This Python script (interface_compliance_check.py) verifies the configuration of network switch interfaces for compliance with predefined templates. It generates detailed reports on non-compliant interfaces and creates configuration files for missing settings. The script also supports proxy functionality for SSH connections.
Features

Checks network switch configurations against predefined templates
Supports flexible template matching based on interface descriptions
Generates detailed compliance reports
Creates configuration files for missing settings
Groups ports with similar compliance issues for easier analysis
Optional: Filters hosts based on hostname prefix
Supports proxy functionality for SSH connections

Prerequisites

Python 3.6+
Nornir
Nornir-Netmiko
Nornir-Utils

Installation

Clone the repository:
Copygit clone https://github.com/your-username/network-compliance-checker.git

Install the required dependencies:
Copypip install nornir nornir-netmiko nornir-utils


Configuration

Create an interface_templates folder and add your template files.

Template files should have the .txt extension.
Each line in the template file represents a required command.
Lines starting with + are additionally allowed commands.
Lines starting with # are comments and will be ignored.


Create a config.yaml file for Nornir with your network device details.
SSH Proxy Configuration:

Create an SSH config file (e.g., ~/.ssh/config) with your proxy settings.
Ensure that the SSH config file includes the necessary Host and ProxyCommand directives for your environment.



Usage
The interface_compliance_check.py script supports the following command-line arguments:

-c or --config: Path to the Nornir configuration file (default: "config.yaml")
-t or --templates: Path to the directory with interface templates (default: "interface_templates")
-f or --filter: Optional filter string for hostname prefix
-o or --output: Directory to store output files (default: current directory)

Examples:

Standard execution (all hosts):
Copypython interface_compliance_check.py

With custom configuration and filtering:
Copypython interface_compliance_check.py -c my_config.yaml -t custom_templates -f switch -o /path/to/output


The script will automatically use the SSH proxy settings defined in your SSH config file when connecting to devices.
Output

A compliance report is saved in the specified output directory.
Configuration files for missing settings are saved in the missing_configs subdirectory of the output directory.

Main Functions

parse_intf_template_files_individually: Reads the template files.
parse_interfaces: Extracts interface configurations from the device configuration.
check_interface_compliance: Checks the compliance of a single interface.
check_switch_compliance: Performs the compliance check for an entire switch.
find_matching_template: Finds the matching template based on the interface description.
generate_missing_config_files: Creates configuration files for missing settings.
generate_report: Generates the compliance report.

Customization
You can customize the script by:

Modifying the template matching logic in find_matching_template.
Adjusting the compliance checking logic in check_interface_compliance.
Customizing the format of the generated report in generate_report.
Modifying the SSH proxy settings in your SSH config file to suit your network environment.

Contributing
Contributions are welcome! Please fork the repository and create a pull request with your changes.


## Contact

herbert.dinnobl@nts.eu