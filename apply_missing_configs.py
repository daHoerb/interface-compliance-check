from nornir import InitNornir
from nornir_utils.plugins.functions import print_result
from nornir_netmiko import netmiko_send_config
import os
import logging
import argparse
from datetime import datetime
import socks
import socket
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def global_config(task, config):
    try:
        r = task.run(
            netmiko_send_config, 
            name='Apply Missing Config', 
            config_file=config, 
            read_timeout=0
        )
        print_result(r)
        return "Success"
    except Exception as e:
        logger.error("Error applying config to {}: {}".format(task.host, str(e)))
        return "Failed: {}".format(str(e))

def apply_missing_configs(nr, config_dir, dry_run=False):
    success_hosts = []
    failed_hosts = []
    skipped_hosts = []

    for filename in os.listdir(config_dir):
        if filename.endswith("_missing_config.txt"):
            hostname = filename.split("_missing_config.txt")[0]
            config_file = os.path.join(config_dir, filename)
            
            host_nr = nr.filter(name=hostname)
            
            if not host_nr.inventory.hosts:
                logger.warning("Host {} not found in inventory. Skipping.".format(hostname))
                skipped_hosts.append(hostname)
                continue
            
            if dry_run:
                logger.info("DRY RUN: Would apply config from {} to {}".format(config_file, hostname))
                with open(config_file, 'r') as f:
                    logger.info("Configuration to be applied:\n{}".format(f.read()))
                success_hosts.append(hostname)
                continue

            logger.info("Applying missing config to {}".format(hostname))
            result = host_nr.run(task=global_config, config=config_file)
            
            if result[hostname][0].result == "Success":
                logger.info("Successfully applied config to {}".format(hostname))
                success_hosts.append(hostname)
            else:
                logger.error("Failed to apply config to {}: {}".format(hostname, result[hostname][0].result))
                failed_hosts.append(hostname)

    return success_hosts, failed_hosts, skipped_hosts

def generate_summary(success_hosts, failed_hosts, skipped_hosts, config_dir, dry_run):
    now = datetime.now()
    summary_file = "config_application_summary_{}.txt".format(now.strftime('%Y%m%d_%H%M%S'))
    
    with open(summary_file, 'w') as f:
        f.write("Configuration Application Summary\n")
        f.write("Generated on: {}\n".format(now.strftime('%Y-%m-%d %H:%M:%S')))
        f.write("Mode: {}\n".format("DRY RUN" if dry_run else "ACTUAL RUN"))
        f.write("Config directory: {}\n\n".format(config_dir))
        
        f.write("Successful Hosts ({}):\n".format(len(success_hosts)))
        for host in success_hosts:
            f.write("- {}\n".format(host))
        
        f.write("\nFailed Hosts ({}):\n".format(len(failed_hosts)))
        for host in failed_hosts:
            f.write("- {}\n".format(host))
        
        f.write("\nSkipped Hosts ({}):\n".format(len(skipped_hosts)))
        for host in skipped_hosts:
            f.write("- {}\n".format(host))
    
    return summary_file

def configure_proxy(host="127.0.0.1", port=1084, enabled=True):
    """Configure SOCKS5 proxy settings"""
    if enabled:
        try:
            socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, host, port)
            socket.socket = socks.socksocket
            print(f"Proxy configured successfully: {host}:{port}")
        except Exception as e:
            print(f"Error configuring proxy: {e}")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Apply missing configurations to network devices")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the Nornir config file (default: config.yaml)")
    parser.add_argument("-d", "--config-dir", default="missing_configs", help="Directory containing the missing config files (default: missing_configs)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without applying configurations")

    # Optional SOCKS5 proxy settigs
    parser.add_argument("--proxy-enabled", action="store_true", help="Enable SOCKS5 proxy")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host (default: 127.0.0.1)")
    parser.add_argument("--proxy-port", type=int, default=1084, help="Proxy port (default: 1084)")

    args = parser.parse_args()

    nr = InitNornir(config_file=args.config)

    # Check proxy Settings
    if args.proxy_enabled:
        if not configure_proxy(args.proxy_host, args.proxy_port):
            print("Failed to configure proxy")
            sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    
    
    success_hosts, failed_hosts, skipped_hosts = apply_missing_configs(nr, args.config_dir, args.dry_run)
    
    summary_file = generate_summary(success_hosts, failed_hosts, skipped_hosts, args.config_dir, args.dry_run)
    
    logger.info("\nSummary report saved to: {}".format(summary_file))
    logger.info("Successful hosts: {}".format(len(success_hosts)))
    logger.info("Failed hosts: {}".format(len(failed_hosts)))
    logger.info("Skipped hosts: {}".format(len(skipped_hosts)))

if __name__ == "__main__":
    main()