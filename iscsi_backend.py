#!/usr/bin/env python3
# iscsi_backend.py

import subprocess
import json
import re
from typing import Dict, List, Optional

class ISCSIBackend:
    def __init__(self):
        self.iqn_prefix = "iqn.2025-09.local.ubuntu"  # Changed to local.ubuntu
    
    def execute_command(self, command: str) -> tuple:
        """Execute shell command and return result"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                executable='/bin/bash'
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)
    
    def get_system_status(self) -> Dict:
        """Get iSCSI system status"""
        services = {}
        
        # Check targetclid service
        returncode, stdout, stderr = self.execute_command("sudo systemctl is-active targetclid")
        services['targetclid'] = 'running' if returncode == 0 else 'stopped'
        
        # Check iscsid service
        returncode, stdout, stderr = self.execute_command("sudo systemctl is-active iscsid")
        services['iscsid'] = 'running' if returncode == 0 else 'stopped'
        
        return services
    
    def get_targets(self) -> List[Dict]:
        """Get all iSCSI targets - CORRECTED VERSION"""
        print("=== GETTING TARGETS (CORRECTED VERSION) ===")
        
        # Extract clean IQNs using the working regex pattern
        cmd = "sudo targetcli ls /iscsi 2>/dev/null"
        returncode, stdout, stderr = self.execute_command(cmd)
        
        targets = []
        
        if returncode == 0 and stdout:
            # Use the working regex pattern to extract clean IQNs
            iqn_pattern = r'o-\s+(iqn\.[^\.\s]+(?:\.[^\.\s]+)*:[^\.\s]+)'
            lines = stdout.split('\n')
            
            current_target = None
            
            for line in lines:
                line = line.strip()
                
                # Look for target lines (main iSCSI targets)
                if line.startswith('o- iqn.') and ('[TPGs:' in line or 'TPGs:' in line):
                    # Save previous target if exists
                    if current_target:
                        targets.append(current_target)
                    
                    # Extract target IQN
                    target_match = re.search(iqn_pattern, line)
                    if target_match:
                        target_iqn = target_match.group(1)
                        current_target = {
                            'iqn': target_iqn,
                            'tpg_groups': ['tpg1'],
                            'luns': [],
                            'acls': [],
                            'portals': [{'ip': '0.0.0.0', 'port': '3260'}],
                            'authentication': False  # Default no authentication
                        }
                        print(f"Found target: {target_iqn}")
                
                # If we have a current target, parse its details
                elif current_target:
                    # Look for LUNs
                    if 'o- lun' in line and 'block/' in line:
                        lun_match = re.search(r'o- lun(\d+)\s+\[([^]]+)\]', line)
                        if lun_match:
                            lun_info = lun_match.group(2)
                            backstore = 'unknown'
                            if 'block/' in lun_info:
                                backstore_match = re.search(r'block/([^\s\(]+)', lun_info)
                                if backstore_match:
                                    backstore = backstore_match.group(1)
                            current_target['luns'].append({
                                'id': lun_match.group(1),
                                'backstore': backstore
                            })
                            print(f"  - LUN {lun_match.group(1)}: {backstore}")
                    
                    # Look for ACLs (client IQNs)
                    elif 'o- iqn.' in line and 'Mapped LUNs' in line:
                        acl_match = re.search(iqn_pattern, line)
                        if acl_match:
                            acl_iqn = acl_match.group(1)
                            current_target['acls'].append(acl_iqn)
                            print(f"  - ACL: {acl_iqn}")
                    
                    # Check authentication status
                    elif 'attribute authentication=' in line:
                        auth_match = re.search(r'authentication=(\d)', line)
                        if auth_match:
                            current_target['authentication'] = auth_match.group(1) == '1'
            
            # Don't forget the last target
            if current_target:
                targets.append(current_target)
        
        print(f"Returning {len(targets)} targets")
        for target in targets:
            print(f"  - {target['iqn']}: {len(target['luns'])} LUNs, {len(target['acls'])} ACLs, Auth: {target['authentication']}")
        
        return targets
    
    def create_target(self, target_name: str, zvol_path: str, enable_auth: bool = False) -> Dict:
        """Create iSCSI target with ZVOL"""
        iqn = f"{self.iqn_prefix}:{target_name}"
        
        # Create backstore
        backstore_cmd = f"sudo targetcli backstores/block create {target_name} {zvol_path}"
        returncode, stdout, stderr = self.execute_command(backstore_cmd)
        if returncode != 0:
            return {'success': False, 'error': f"Backstore creation failed: {stderr}"}
        
        # Create target
        target_cmd = f"sudo targetcli iscsi/ create {iqn}"
        returncode, stdout, stderr = self.execute_command(target_cmd)
        if returncode != 0:
            return {'success': False, 'error': f"Target creation failed: {stderr}"}
        
        # Create LUN
        lun_cmd = f"sudo targetcli iscsi/{iqn}/tpg1/luns/ create /backstores/block/{target_name}"
        returncode, stdout, stderr = self.execute_command(lun_cmd)
        if returncode != 0:
            return {'success': False, 'error': f"LUN creation failed: {stderr}"}
        
        # Create portal
        portal_cmd = f"sudo targetcli iscsi/{iqn}/tpg1/portals/ create 0.0.0.0"
        returncode, stdout, stderr = self.execute_command(portal_cmd)
        if returncode != 0:
            return {'success': False, 'error': f"Portal creation failed: {stderr}"}
        
        # Set attributes (authentication disabled by default, allow all)
        auth_value = 1 if enable_auth else 0
        attr_cmd = f"sudo targetcli iscsi/{iqn}/tpg1 set attribute authentication={auth_value} demo_mode_write_protect=0 generate_node_acls=1 cache_dynamic_acls=1"
        self.execute_command(attr_cmd)
        
        # Save config
        self.execute_command("sudo targetcli saveconfig")
        
        return {'success': True, 'message': f"Target {iqn} created successfully"}
    
    def delete_target(self, target_iqn: str) -> Dict:
        """Delete iSCSI target"""
        # Extract target name from IQN for backstore cleanup
        target_name = target_iqn.split(':')[-1]
        
        # Delete target
        target_cmd = f"sudo targetcli iscsi/ delete {target_iqn}"
        returncode, stdout, stderr = self.execute_command(target_cmd)
        if returncode != 0:
            return {'success': False, 'error': f"Target deletion failed: {stderr}"}
        
        # Delete backstore
        backstore_cmd = f"sudo targetcli backstores/block delete {target_name}"
        self.execute_command(backstore_cmd)
        
        # Save config
        self.execute_command("sudo targetcli saveconfig")
        
        return {'success': True, 'message': f"Target {target_iqn} deleted successfully"}
    
    def add_acl(self, target_iqn: str, client_iqn: str) -> Dict:
        """Add ACL for specific client"""
        acl_cmd = f"sudo targetcli iscsi/{target_iqn}/tpg1/acls/ create {client_iqn}"
        returncode, stdout, stderr = self.execute_command(acl_cmd)
        
        if returncode == 0:
            # Disable automatic ACL generation
            attr_cmd = f"sudo targetcli iscsi/{target_iqn}/tpg1 set attribute generate_node_acls=0"
            self.execute_command(attr_cmd)
            self.execute_command("sudo targetcli saveconfig")
            return {'success': True, 'message': f"ACL for {client_iqn} added"}
        else:
            return {'success': False, 'error': f"ACL creation failed: {stderr}"}
    
    def remove_acl(self, target_iqn: str, client_iqn: str) -> Dict:
        """Remove ACL"""
        acl_cmd = f"sudo targetcli iscsi/{target_iqn}/tpg1/acls/ delete {client_iqn}"
        returncode, stdout, stderr = self.execute_command(acl_cmd)
        
        if returncode == 0:
            self.execute_command("sudo targetcli saveconfig")
            return {'success': True, 'message': f"ACL for {client_iqn} removed"}
        else:
            return {'success': False, 'error': f"ACL removal failed: {stderr}"}

# Singleton instance
iscsi_backend = ISCSIBackend()
