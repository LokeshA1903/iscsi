#!/usr/bin/env python3
# zfs_manager.py

import subprocess
import json
import re
from typing import Dict, List, Optional

class ZFSManager:
    def __init__(self):
        self.pool_name = "tank"  # Default pool name
    
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
    
    def get_pool_status(self) -> Dict:
        """Get ZFS pool status"""
        returncode, stdout, stderr = self.execute_command("sudo zpool status")
        return {
            'status': 'success' if returncode == 0 else 'error',
            'output': stdout,
            'error': stderr
        }
    
    def list_pools(self) -> List[Dict]:
        """List all ZFS pools"""
        returncode, stdout, stderr = self.execute_command("sudo zpool list -H -o name,size,alloc,free,health")
        pools = []
        if returncode == 0:
            for line in stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    pools.append({
                        'name': parts[0],
                        'size': parts[1],
                        'allocated': parts[2],
                        'free': parts[3],
                        'health': parts[4]
                    })
        return pools
    
    def list_datasets(self, pool_name: str = None) -> List[Dict]:
        """List ZFS datasets and volumes from ALL pools or specific pool"""
        if pool_name:
            # List datasets from specific pool
            returncode, stdout, stderr = self.execute_command(f"sudo zfs list -r -o name,used,avail,refer,mountpoint,type -H {pool_name}")
        else:
            # List datasets from ALL pools
            returncode, stdout, stderr = self.execute_command("sudo zfs list -r -o name,used,avail,refer,mountpoint,type -H")
        
        datasets = []
        if returncode == 0:
            for line in stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    datasets.append({
                        'name': parts[0],
                        'used': parts[1],
                        'available': parts[2],
                        'referenced': parts[3],
                        'mountpoint': parts[4],
                        'type': parts[5]
                    })
        return datasets
    
    def get_available_zvols(self, pool_name: str = None) -> List[Dict]:
        """Get available ZFS volumes that are not configured in iSCSI"""
        from iscsi_backend import iscsi_backend
        
        # Get all volumes from all pools or specific pool
        all_datasets = self.list_datasets(pool_name)
        volumes = [ds for ds in all_datasets if ds['type'] == 'volume']
        
        # Get configured iSCSI targets to exclude already used volumes
        configured_targets = iscsi_backend.get_targets()
        configured_volumes = []
        
        for target in configured_targets:
            for lun in target.get('luns', []):
                backstore = lun.get('backstore', '')
                if backstore and backstore != 'unknown':
                    configured_volumes.append(backstore)
        
        # Filter out configured volumes
        available_volumes = []
        for volume in volumes:
            vol_name = volume['name'].split('/')[-1]
            if vol_name not in configured_volumes:
                available_volumes.append(volume)
        
        return available_volumes
    
    def create_zvol(self, name: str, size: str, pool: str = None) -> Dict:
        """Create a ZFS volume"""
        pool = pool or self.pool_name
        volname = f"{pool}/{name}"
        returncode, stdout, stderr = self.execute_command(f"sudo zfs create -V {size} {volname}")
        return {
            'success': returncode == 0,
            'message': f"Volume {volname} created successfully" if returncode == 0 else f"Error: {stderr}",
            'volume_path': f"/dev/zvol/{volname}" if returncode == 0 else None
        }
    
    def delete_zvol(self, name: str, pool: str = None) -> Dict:
        """Delete a ZFS volume"""
        pool = pool or self.pool_name
        volname = f"{pool}/{name}"
        returncode, stdout, stderr = self.execute_command(f"sudo zfs destroy {volname}")
        return {
            'success': returncode == 0,
            'message': f"Volume {volname} deleted successfully" if returncode == 0 else f"Error: {stderr}"
        }
    
    def resize_zvol(self, name: str, new_size: str, pool: str = None) -> Dict:
        """Resize a ZFS volume"""
        pool = pool or self.pool_name
        volname = f"{pool}/{name}"
        returncode, stdout, stderr = self.execute_command(f"sudo zfs set volsize={new_size} {volname}")
        return {
            'success': returncode == 0,
            'message': f"Volume {volname} resized to {new_size}" if returncode == 0 else f"Error: {stderr}"
        }
    
    def create_snapshot(self, dataset: str, snapshot_name: str) -> Dict:
        """Create a ZFS snapshot"""
        snapshot_full = f"{dataset}@{snapshot_name}"
        returncode, stdout, stderr = self.execute_command(f"sudo zfs snapshot {snapshot_full}")
        return {
            'success': returncode == 0,
            'message': f"Snapshot {snapshot_full} created successfully" if returncode == 0 else f"Error: {stderr}"
        }
    
    def list_snapshots(self, dataset: str = None) -> List[Dict]:
        """List ZFS snapshots from ALL datasets or specific dataset"""
        if dataset:
            target = dataset
        else:
            # List snapshots from all datasets
            target = "-r -t snapshot"
        
        returncode, stdout, stderr = self.execute_command(f"sudo zfs list -o name,creation,used,refer -H {target}")
        snapshots = []
        if returncode == 0:
            for line in stdout.strip().split('\n'):
                if line and '@' in line:
                    parts = line.split('\t')
                    snapshots.append({
                        'name': parts[0],
                        'creation': parts[1],
                        'used': parts[2],
                        'referenced': parts[3]
                    })
        return snapshots
    
    def delete_snapshot(self, snapshot_name: str) -> Dict:
        """Delete a ZFS snapshot"""
        returncode, stdout, stderr = self.execute_command(f"sudo zfs destroy {snapshot_name}")
        return {
            'success': returncode == 0,
            'message': f"Snapshot {snapshot_name} deleted successfully" if returncode == 0 else f"Error: {stderr}"
        }
    
    def rollback_snapshot(self, snapshot_name: str) -> Dict:
        """Rollback to a snapshot"""
        returncode, stdout, stderr = self.execute_command(f"sudo zfs rollback {snapshot_name}")
        return {
            'success': returncode == 0,
            'message': f"Rolled back to {snapshot_name}" if returncode == 0 else f"Error: {stderr}"
        }
    
    def clone_snapshot(self, snapshot_name: str, clone_name: str) -> Dict:
        """Clone a snapshot to a new dataset"""
        returncode, stdout, stderr = self.execute_command(f"sudo zfs clone {snapshot_name} {clone_name}")
        return {
            'success': returncode == 0,
            'message': f"Clone {clone_name} created from {snapshot_name}" if returncode == 0 else f"Error: {stderr}"
        }
    
    def get_compression_info(self, dataset: str = None) -> Dict:
        """Get compression information for all pools or specific dataset"""
        if dataset:
            target = dataset
        else:
            # Get compression info for all pools
            pools = self.list_pools()
            if pools:
                target = pools[0]['name']  # Use first pool for general info
            else:
                return {}
        
        returncode, stdout, stderr = self.execute_command(f"sudo zfs get compression,compressratio -H {target}")
        info = {}
        if returncode == 0:
            for line in stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if 'compression' in parts[1]:
                        info['compression'] = parts[2]
                    elif 'compressratio' in parts[1]:
                        info['compressratio'] = parts[2]
        return info

# Singleton instance
zfs_manager = ZFSManager()
