# ==============================================================================
# STAGE 1: THE BUILDER (Compiles tools from source)
# ==============================================================================
FROM rockylinux:9 as builder

# Install Build Dependencies
RUN dnf groupinstall -y "Development Tools" && \
    dnf install -y \
    epel-release \
    numactl-devel \
    libaio-devel \
    boost-devel \
    openssl-devel \
    zlib-devel \
    libuuid-devel \
    libcurl-devel \
    python3-devel \
    ncurses-devel \
    cmake \
    git \
    wget \
    m4 autoconf automake libtool \
    && dnf clean all

WORKDIR /build

# --- Compile DOOL ---
RUN git clone https://github.com/scottchiefbaker/dool.git

# --- Compile FIO ---
RUN git clone https://github.com/axboe/fio.git && \
    cd fio && ./configure && make -j$(nproc) && make install DESTDIR=/build/install

# --- Compile iPerf ---
RUN git clone https://github.com/esnet/iperf.git && \
    cd iperf && ./configure --prefix=/usr/local && make -j$(nproc) && make install DESTDIR=/build/install

# --- Compile SockPerf ---
RUN git clone https://github.com/mellanox/sockperf && \
    cd sockperf && ./autogen.sh && ./configure --prefix=/usr/local && make -j$(nproc) && make install DESTDIR=/build/install

# --- Compile Elbencho ---
RUN git clone https://github.com/breuner/elbencho.git && \
    cd elbencho && \
    make S3_SUPPORT=1 -j$(nproc) && \
    make install DESTDIR=/build/install

# ==============================================================================
# STAGE 2: THE FINAL IMAGE (Runtime only)
# ==============================================================================
FROM rockylinux:9

# 1. Install Runtime Dependencies
RUN dnf install -y epel-release && \
    dnf install -y --allowerasing \
    # --- HARDWARE & SYSTEM ---
    ipmitool \
    OpenIPMI \
    nvme-cli \
    smartmontools \
    pciutils \
    sg3_utils \
    lsof \
    strace \
    sysstat \
    procps-ng \
    htop \
    numactl \
    # --- NETWORK ---
    nmap-ncat \
    socat \
    telnet \
    tcpdump \
    ethtool \
    mtr \
    traceroute \
    iproute \
    bind-utils \
    # --- STORAGE & CLOUD (Added s3cmd) ---
    s3cmd \
    # --- LIBRARIES ---
    libaio \
    boost-program-options \
    boost-system \
    boost-thread \
    openssl \
    libuuid \
    zlib \
    python3 \
    libcurl \
    ncurses \
    libibverbs \
    librdmacm \
    && dnf clean all

# 2. Copy compiled binaries from the Builder Stage
COPY --from=builder /build/install/usr/local/bin /usr/local/bin
COPY --from=builder /build/install/usr/local/lib /usr/local/lib
COPY --from=builder /build/dool /opt/dool

# 3. Setup Environment for Dool and Libraries
RUN ln -s /opt/dool/dool /usr/local/bin/dool && \
    echo "/usr/local/lib" > /etc/ld.so.conf.d/local.conf && \
    ldconfig

# 4. Create Sample s3cfg
# We create a template optimized for VAST (S3 style)
RUN printf "[default]\n\
access_key = CHANGE_ME\n\
secret_key = CHANGE_ME\n\
host_base = vast-vip-pool.example.com\n\
host_bucket = %%(bucket)s.vast-vip-pool.example.com\n\
use_https = True\n\
check_ssl_certificate = False\n\
check_ssl_hostname = False\n\
signature_v2 = False\n\
" > /root/s3cfg-template

# 5. Aliases & Auto-Config
RUN echo "alias la='ls -Av'" >> /root/.bashrc && \
    echo "alias ll='ls -lhvF --group-directories-first'" >> /root/.bashrc && \
    echo "alias lla='ls -lahvF --group-directories-first'" >> /root/.bashrc && \
    echo "alias egrep='egrep --color=auto'" >> /root/.bashrc && \
    echo "alias grep='grep --color=auto'" >> /root/.bashrc && \
    echo "alias df='df -kh'" >> /root/.bashrc && \
    echo "set -o vi" >> /root/.bashrc && \
    # Auto-copy the s3cfg template if one doesn't exist
    echo "if [ ! -f ~/.s3cfg ]; then cp ~/s3cfg-template ~/.s3cfg; fi" >> /root/.bashrc

# 6. README & Entry
WORKDIR /root
RUN printf "================================================================================\n\
                    VAST DATA DIAGNOSTIC TOOLBOX (LITE)\n\
================================================================================\n\
\n\
INSTALLED TOOLS:\n\
----------------\n\
  * Hardware: ipmitool, nvme-cli, smartctl, sg_utils\n\
  * Storage:  fio, elbencho, s3cmd\n\
  * Network:  nc, iperf3, sockperf, tcpdump, ethtool, ip, ss\n\
  * System:   htop, strace, lsof, numactl, pidstat, dstat, dool\n\
\n\
S3 CONFIGURATION:\n\
-----------------\n\
  A default .s3cfg file has been created in /root/.s3cfg.\n\
  Edit it to set your VAST Access Key, Secret Key, and Endpoint:\n\
  > vi ~/.s3cfg\n\
\n\
ACCESSING THE HOST:\n\
-------------------\n\
  1. IPMI: ipmitool sdr list (Requires --privileged)\n\
  2. HOST ROOT: /host-root (Read-Only)\n\
  3. BENCH TARGET: /bench-target (Read-Write)\n\
\n\
================================================================================\n" > /root/README.txt

RUN echo "cat /root/README.txt" >> /root/.bashrc

CMD ["/bin/bash"]