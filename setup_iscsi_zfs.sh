#!/bin/bash
# setup_iscsi_zfs.sh

echo "=== ZFS iSCSI Manager Setup ==="

# Update system
echo "Updating system packages..."
sudo apt update

# Install required packages
echo "Installing required packages..."
sudo apt install -y \
    targetcli-fb \
    open-iscsi \
    zfsutils-linux \
    python3-pip \
    python3-venv \
    python3-full

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv iscsi_venv

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source iscsi_venv/bin/activate
pip install flask python-dotenv gunicorn

# Start services
echo "Starting services..."
sudo systemctl enable targetclid
sudo systemctl start targetclid
sudo systemctl enable iscsid
sudo systemctl start iscsid

# Configure sudo permissions
echo "Configuring sudo permissions..."
sudo tee /etc/sudoers.d/iscsi-zfs > /dev/null << 'EOF'
%sudo ALL=(ALL) NOPASSWD: /usr/bin/targetcli
%sudo ALL=(ALL) NOPASSWD: /sbin/zfs
%sudo ALL=(ALL) NOPASSWD: /sbin/zpool
%sudo ALL=(ALL) NOPASSWD: /bin/dd
%sudo ALL=(ALL) NOPASSWD: /bin/systemctl
EOF

sudo chmod 440 /etc/sudoers.d/iscsi-zfs

# Create project structure
echo "Creating project structure..."
mkdir -p templates static/css static/js

echo "=== Setup Complete ==="
echo ""
echo "To start the application:"
echo "  source iscsi_venv/bin/activate"
echo "  python3 app.py"
echo ""
echo "Access at: http://localhost:5000"
echo ""
echo "For production use:"
echo "  gunicorn -w 4 -b 0.0.0.0:5000 app:app"
