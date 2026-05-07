FROM osgeo/gdal:ubuntu-small-3.9.0

# tippecanoe + pmtiles CLI + rclone for CI/CD PMTiles builds
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        build-essential \
        libsqlite3-dev \
        zlib1g-dev \
        curl \
        ca-certificates \
        git && \
    # tippecanoe from source (no apt package in ubuntu-small base)
    git clone --depth 1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe && \
    cd /tmp/tippecanoe && \
    make -j"$(nproc)" && \
    make install && \
    cd / && rm -rf /tmp/tippecanoe && \
    # pmtiles CLI
    PMTILES_VER=$(curl -fsSL https://api.github.com/repos/protomaps/go-pmtiles/releases/latest | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/') && \
    curl -fsSL "https://github.com/protomaps/go-pmtiles/releases/download/v${PMTILES_VER}/go-pmtiles_${PMTILES_VER}_Linux_x86_64.tar.gz" \
        | tar -xz -C /usr/local/bin pmtiles && \
    # rclone
    curl -fsSL https://rclone.org/install.sh | bash && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
ENTRYPOINT ["bash", "infra/pmtiles/build.sh"]
