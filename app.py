
#!/usr/bin/env python3
# app.py

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from iscsi_backend import iscsi_backend
from zfs_manager import zfs_manager
import json
import os
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change in production

# Helper functions for ZFS operations
def get_zfs_datasets():
    """Get ZFS datasets"""
    return zfs_manager.list_datasets()

def get_zfs_snapshots():
    """Get ZFS snapshots"""
    return zfs_manager.list_snapshots()

# Schedule Database Setup
def init_schedule_db():
    """Initialize the schedule database"""
    conn = sqlite3.connect('schedules.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dataset TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            retention_days INTEGER DEFAULT 7,
            enabled BOOLEAN DEFAULT 1,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database when app starts
init_schedule_db()

@app.route('/')
def dashboard():
    """Main dashboard"""
    # Get system status
    iscsi_status = iscsi_backend.get_system_status()
    zfs_pools = zfs_manager.list_pools()
    zfs_status = zfs_manager.get_pool_status()
    
    return render_template('dashboard.html', 
                         iscsi_status=iscsi_status,
                         zfs_pools=zfs_pools,
                         zfs_status=zfs_status)

@app.route('/targets')
def targets():
    """iSCSI targets management"""
    targets_list = iscsi_backend.get_targets()
    zfs_pools = zfs_manager.list_pools()
    
    return render_template('targets.html', 
                         targets=targets_list,
                         zfs_pools=zfs_pools)

@app.route('/api/targets', methods=['GET'])
def api_get_targets():
    """API: Get all targets"""
    targets = iscsi_backend.get_targets()
    return jsonify(targets)

@app.route('/api/targets/create', methods=['POST'])
def api_create_target():
    """API: Create new target"""
    data = request.json
    target_name = data.get('name')
    zvol_name = data.get('zvol_name')
    pool_name = data.get('pool_name', 'tank')
    enable_auth = data.get('enable_auth', False)
    
    zvol_path = f"/dev/zvol/{pool_name}/{zvol_name}"
    result = iscsi_backend.create_target(target_name, zvol_path, enable_auth)
    
    return jsonify(result)

@app.route('/api/targets/delete', methods=['POST'])
def api_delete_target():
    """API: Delete target"""
    data = request.json
    target_iqn = data.get('target_iqn')
    
    result = iscsi_backend.delete_target(target_iqn)
    return jsonify(result)

@app.route('/api/targets/acl/add', methods=['POST'])
def api_add_acl():
    """API: Add ACL"""
    data = request.json
    target_iqn = data.get('target_iqn')
    client_iqn = data.get('client_iqn')
    
    result = iscsi_backend.add_acl(target_iqn, client_iqn)
    return jsonify(result)

@app.route('/api/targets/acl/remove', methods=['POST'])
def api_remove_acl():
    """API: Remove ACL"""
    data = request.json
    target_iqn = data.get('target_iqn')
    client_iqn = data.get('client_iqn')
    
    result = iscsi_backend.remove_acl(target_iqn, client_iqn)
    return jsonify(result)

@app.route('/zfs')
def zfs_management():
    """ZFS management"""
    pools = zfs_manager.list_pools()
    datasets = zfs_manager.list_datasets()
    snapshots = zfs_manager.list_snapshots()
    compression_info = zfs_manager.get_compression_info()
    
    return render_template('zfs.html',
                         pools=pools,
                         datasets=datasets,
                         snapshots=snapshots,
                         compression_info=compression_info)

@app.route('/api/zfs/pools', methods=['GET'])
def api_get_pools():
    """API: Get ZFS pools"""
    pools = zfs_manager.list_pools()
    return jsonify(pools)

@app.route('/api/zfs/datasets', methods=['GET'])
def api_get_datasets():
    """API: Get ZFS datasets"""
    datasets = zfs_manager.list_datasets()
    return jsonify(datasets)

@app.route('/api/zfs/zvols/available', methods=['GET'])
def api_get_available_zvols():
    """API: Get available ZFS volumes (not configured in iSCSI)"""
    pool_name = request.args.get('pool_name')
    available_zvols = zfs_manager.get_available_zvols(pool_name)
    return jsonify(available_zvols)

@app.route('/api/zfs/zvol/create', methods=['POST'])
def api_create_zvol():
    """API: Create ZVOL"""
    data = request.json
    name = data.get('name')
    size = data.get('size')
    pool = data.get('pool', 'tank')
    
    result = zfs_manager.create_zvol(name, size, pool)
    return jsonify(result)

@app.route('/api/zfs/zvol/delete', methods=['POST'])
def api_delete_zvol():
    """API: Delete ZVOL"""
    data = request.json
    name = data.get('name')
    pool = data.get('pool', 'tank')
    
    result = zfs_manager.delete_zvol(name, pool)
    return jsonify(result)

@app.route('/api/zfs/zvol/resize', methods=['POST'])
def api_resize_zvol():
    """API: Resize ZVOL"""
    data = request.json
    name = data.get('name')
    new_size = data.get('new_size')
    pool = data.get('pool', 'tank')
    
    result = zfs_manager.resize_zvol(name, new_size, pool)
    return jsonify(result)

@app.route('/api/zfs/snapshot/create', methods=['POST'])
def api_create_snapshot():
    """API: Create snapshot"""
    data = request.json
    dataset = data.get('dataset')
    snapshot_name = data.get('snapshot_name')
    
    result = zfs_manager.create_snapshot(dataset, snapshot_name)
    return jsonify(result)

@app.route('/api/zfs/snapshot/delete', methods=['POST'])
def api_delete_snapshot():
    """API: Delete snapshot"""
    data = request.json
    snapshot_name = data.get('snapshot_name')
    
    result = zfs_manager.delete_snapshot(snapshot_name)
    return jsonify(result)

@app.route('/api/zfs/snapshot/rollback', methods=['POST'])
def api_rollback_snapshot():
    """API: Rollback snapshot"""
    data = request.json
    snapshot_name = data.get('snapshot_name')
    
    result = zfs_manager.rollback_snapshot(snapshot_name)
    return jsonify(result)

@app.route('/api/zfs/snapshot/clone', methods=['POST'])
def api_clone_snapshot():
    """API: Clone snapshot"""
    data = request.json
    snapshot_name = data.get('snapshot_name')
    clone_name = data.get('clone_name')
    
    result = zfs_manager.clone_snapshot(snapshot_name, clone_name)
    return jsonify(result)

@app.route('/snapshots')
def snapshots():
    """Snapshots management"""
    try:
        snapshots_list = zfs_manager.list_snapshots()
        datasets = zfs_manager.list_datasets()
        
        return render_template('snapshots.html',
                            snapshots=snapshots_list,
                            datasets=datasets)
    except Exception as e:
        flash(f'Error loading snapshots: {str(e)}', 'error')
        return render_template('snapshots.html', snapshots=[], datasets=[])

# Schedule Management Routes
@app.route('/api/schedules', methods=['GET'])
def api_get_schedules():
    """API: Get all schedules"""
    try:
        conn = sqlite3.connect('schedules.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM schedules ORDER BY created_at DESC')
        
        schedules = []
        for row in cursor.fetchall():
            schedules.append({
                'id': row['id'],
                'name': row['name'],
                'dataset': row['dataset'],
                'schedule_type': row['schedule_type'],
                'cron_expression': row['cron_expression'],
                'retention_days': row['retention_days'],
                'enabled': bool(row['enabled']),
                'last_run': row['last_run'],
                'next_run': row['next_run'],
                'created_at': row['created_at']
            })
        
        conn.close()
        return jsonify(schedules)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/schedules/create', methods=['POST'])
def api_create_schedule():
    """API: Create new schedule"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'dataset', 'schedule_type', 'cron_expression']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Missing required field: {field}'})
        
        conn = sqlite3.connect('schedules.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO schedules (name, dataset, schedule_type, cron_expression, retention_days)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['dataset'],
            data['schedule_type'],
            data['cron_expression'],
            data.get('retention_days', 7)
        ))
        
        conn.commit()
        schedule_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Schedule created successfully', 
            'schedule_id': schedule_id
        })
    
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Schedule name already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/schedules/toggle', methods=['POST'])
def api_toggle_schedule():
    """API: Toggle schedule enabled/disabled"""
    try:
        data = request.json
        
        if not data.get('schedule_id'):
            return jsonify({'success': False, 'message': 'Missing schedule_id'})
        
        conn = sqlite3.connect('schedules.db')
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE schedules SET enabled = ? WHERE id = ?', 
            (data['enabled'], data['schedule_id'])
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Schedule updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/schedules/delete', methods=['POST'])
def api_delete_schedule():
    """API: Delete schedule"""
    try:
        data = request.json
        
        if not data.get('schedule_id'):
            return jsonify({'success': False, 'message': 'Missing schedule_id'})
        
        conn = sqlite3.connect('schedules.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM schedules WHERE id = ?', (data['schedule_id'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Schedule deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/schedules/run-now', methods=['POST'])
def api_run_schedule_now():
    """API: Run schedule immediately"""
    try:
        data = request.json
        
        if not data.get('schedule_id'):
            return jsonify({'success': False, 'message': 'Missing schedule_id'})
        
        # Get schedule details
        conn = sqlite3.connect('schedules.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM schedules WHERE id = ?', (data['schedule_id'],))
        schedule = cursor.fetchone()
        
        if schedule:
            # Create snapshot
            snapshot_name = f"schedule-{schedule[1]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            result = zfs_manager.create_snapshot(schedule[2], snapshot_name)
            
            if result['success']:
                # Update last run time
                cursor.execute(
                    'UPDATE schedules SET last_run = ? WHERE id = ?', 
                    (datetime.now(), data['schedule_id'])
                )
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Schedule executed successfully'})
        
        conn.close()
        return jsonify({'success': False, 'message': 'Failed to execute schedule'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/system/status', methods=['GET'])
def api_system_status():
    """API: Get system status"""
    iscsi_status = iscsi_backend.get_system_status()
    zfs_status = zfs_manager.get_pool_status()
    
    return jsonify({
        'iscsi': iscsi_status,
        'zfs': zfs_status
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
