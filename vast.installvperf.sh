#!/bin/bash
### Install and run vperfsanity on a VAST cluster
### Run this on any cnode as the standard user
###

VIP_pool="protocolsPool"

# You might need these
# Check if wget and bc are installed
command -v wget >/dev/null 2>&1 || { echo >&2 "wget is not installed. Installing..."; sudo dnf install -y wget; }
command -v bc >/dev/null 2>&1 || { echo >&2 "bc is not installed. Installing..."; sudo dnf install -y bc; }

# Download and untar
wget https://vast-vperfsanity.s3.amazonaws.com/download/vperfsanity-latest-stable.tar.gz .
tar xf vperfsanity-latest-stable.tar.gz

# Prepare and run it
cd vperfsanity
./vperfsanity_prepare.sh $VIP_pool
./vperfsanity_run.sh -w -r -s 1024 $VIP_pool
