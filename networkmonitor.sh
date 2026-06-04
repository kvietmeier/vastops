#!/bin/bash
#==============================================================================
# Script:      nic_diagnostic.sh
# Description: Captures network and CPU baselines to identify cloud network 
#              throttling, bandwidth limits, and PPS credit exhaustion.
# Usage:       ./nic_diagnostic.sh <interface> <duration_in_seconds>
#==============================================================================

# Usage check
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <interface> <duration_in_seconds>"
    echo "Example: $0 eth0 60"
    exit 1
fi

IFACE=$1
DURATION=$2
LOGDIR="nic_diag_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOGDIR"

echo "=================================================="
echo " Starting Network Diagnostic on $IFACE for $DURATION seconds..."
echo " Output will be saved to directory: $LOGDIR/"
echo "=================================================="

# 1. Check for required tools
for cmd in sar mpstat ethtool; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: '$cmd' is not installed. Please install 'sysstat' and 'ethtool'."
        exit 1
    fi
done

# 2. Capture Pre-Test Baseline
echo "Capturing baseline metrics..."
ip -s link show $IFACE > "$LOGDIR/ip_link_before.txt"
ethtool -S $IFACE > "$LOGDIR/ethtool_before.txt"
cat /proc/softirqs | grep NET_RX > "$LOGDIR/softirqs_before.txt"

# 3. Start Live Monitoring (in background)
echo "Running load monitoring (sar and mpstat)..."
sar -n DEV 1 $DURATION > "$LOGDIR/sar_pps.txt" 2>/dev/null &
SAR_PID=$!

mpstat -P ALL 1 $DURATION > "$LOGDIR/mpstat_cpu.txt" 2>/dev/null &
MP_PID=$!

# Wait for the duration of the test
sleep $DURATION

# Wait for background processes to finish safely
wait $SAR_PID
wait $MP_PID

# 4. Capture Post-Test Metrics
echo "Capturing post-test metrics..."
ip -s link show $IFACE > "$LOGDIR/ip_link_after.txt"
ethtool -S $IFACE > "$LOGDIR/ethtool_after.txt"
cat /proc/softirqs | grep NET_RX > "$LOGDIR/softirqs_after.txt"

# 5. Generate Quick Summary
SUMMARY_FILE="$LOGDIR/00_SUMMARY.txt"
echo "================ SUMMARY REPORT ================" > $SUMMARY_FILE
echo "Test Interface: $IFACE" >> $SUMMARY_FILE
echo "Duration: $DURATION seconds" >> $SUMMARY_FILE
echo "" >> $SUMMARY_FILE

echo "--- Interface Errors/Drops (ip link) ---" >> $SUMMARY_FILE
echo "BEFORE:" >> $SUMMARY_FILE
grep -A 1 "RX:" "$LOGDIR/ip_link_before.txt" | tail -n 1 >> $SUMMARY_FILE
echo "AFTER:" >> $SUMMARY_FILE
grep -A 1 "RX:" "$LOGDIR/ip_link_after.txt" | tail -n 1 >> $SUMMARY_FILE
echo "" >> $SUMMARY_FILE

echo "--- Hardware Ring Buffer Drops (ethtool) ---" >> $SUMMARY_FILE
echo "Look for 'drop', 'missed', or 'error' counters that increased:" >> $SUMMARY_FILE
# Simple diff to find changed lines containing 'drop' or 'error'
diff "$LOGDIR/ethtool_before.txt" "$LOGDIR/ethtool_after.txt" | grep -iE 'drop|error|missed' >> $SUMMARY_FILE

echo "=================================================="
echo " Diagnostic complete! "
echo " Please review the files in $LOGDIR/"
echo " Start by reading $LOGDIR/00_SUMMARY.txt"
echo "=================================================="