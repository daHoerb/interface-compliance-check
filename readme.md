# Network Interface Configuration Management

This repository contains two Python scripts for managing network interface configurations:

1. `interface_compliance_check.py`: Checks interface configurations against templates
2. `apply_missing_configs.py`: Applies missing configurations to network devices

## Features

### Interface Compliance Check
- Validates interface configurations against predefined templates
- Supports flexible template matching based on interface descriptions
- Generates HTML compliance reports
- Creates missing configuration files
- Supports SOCKS5 proxy
- Configurable via YAML and command line arguments

### Apply Missing Configs
- Applies missing configurations to network devices
- Supports dry-run mode
- Generates detailed summary reports
- Handles configuration rollout safely
- Tracks successful, failed, and skipped hosts

## Prerequisites

- Python 3.6+
- Required Python packages (see requirements.txt)
- Network access to target devices
- SSH access configured (if using proxy)

## Installation

1. Clone the repository:
```bash
git clone https://gitlab.nts.at/Herbert.Dinnobl/interface-compliance-check.git
cd interface-compliance-check.git
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Configuration

### Directory Structure
```
.
├── config.yaml
├── Inventory/
│   ├── hosts.yaml
│   ├── groups.yaml
│   └── defaults.yaml
└── interface_templates/
```

### Config File Setup
Create a `config.yaml` file with your Nornir settings:
```yaml
inventory:
    plugin: SimpleInventory
    options:
        host_file: "Inventory/hosts.yaml"
        group_file: "Inventory/groups.yaml"
        defaults_file: "Inventory/defaults.yaml"
runner:
    plugin: serial
options:
    num_workers: 3
```

### Inventory Files
1. `hosts.yaml`: Define your network devices
```yaml
switch1:
    hostname: switch1.example.com
    groups:
        - cisco_ios
```

2. `groups.yaml`: Define device groups and their settings
```yaml
cisco_ios:
    platform: ios
    connection_options:
        netmiko:
            platform: cisco_ios
            extras:
                secret: ""
```

3. `defaults.yaml`: Set default credentials and settings
```yaml
---
username: your_username
password: your_password
platform: ios
```

## Usage

### Interface Compliance Check
```bash
# Basic usage
python interface_compliance_check.py

# With custom config
python interface_compliance_check.py -c custom_config.yaml

# With proxy enabled
python interface_compliance_check.py --proxy-enabled

# With host filter
python interface_compliance_check.py -f switch
```

### Apply Missing Configurations
```bash
# Basic usage
python apply_missing_configs.py

# Dry run mode
python apply_missing_configs.py --dry-run

# With custom config directory
python apply_missing_configs.py -d custom_configs_dir
```

## Output Files

### Compliance Check
- HTML report: `compliance_report_YYYYMMDD_HHMMSS.html`
- Missing configs: `missing_configs/<hostname>_missing_config.txt`

### Apply Configs
- Summary report: `config_application_summary_YYYYMMDD_HHMMSS.txt`

## Interface Templates
Templates should be stored in the `interface_templates` directory with `.txt` extension.
- Lines starting with `+` are additionally allowed commands
- Lines starting with `-` are commands to be removed
- Lines starting with `#` are comments

Example template:
```text
switchport mode access
switchport access vlan 10
+description
-switchport voice vlan
```

## Security Notes
- Store sensitive credentials in `defaults.yaml`
- Use environment variables for production
- Always use dry-run mode first when applying configurations
- Consider using SSH keys instead of passwords

## Contributing
Contributions are welcome! Please feel free to submit pull requests.

## Authors
Herbert Dinnobl

## Support
herbert.dinnobl@nts.eu
