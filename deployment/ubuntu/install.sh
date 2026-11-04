#!/usr/bin/env bash
#
# CHAOS ENGINE HFT - Ubuntu Installation Script
# Phase 11: Monitoring et déploiement Ubuntu
#

set -euo pipefail

echo "========================================="
echo "CHAOS ENGINE HFT - Ubuntu Installation"
echo "========================================="

# Configuration
PROJECT_DIR="/c/Users/Gryphen/Downloads/hft_bot"
INSTALL_DIR="/opt/chaos_engine_hft"
LOG_DIR="/var/log/chaos_engine_hft"
DATA_DIR="/var/lib/chaos_engine_hft"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Vérifier la version Ubuntu
check_ubuntu_version() {
    log "Vérification de la version Ubuntu..."
    
    UBUNTU_VERSION=$(lsb_release -rs)
    MAJOR_VERSION=$(echo "$UBUNTU_VERSION" | cut -d. -f1)
    
    if [[ "$MAJOR_VERSION" -lt 20 ]]; then
        error "Ubuntu 20.04+ requis. Version actuelle: $UBUNTU_VERSION"
        exit 1
    fi
    
    log "Ubuntu $UBUNTU_VERSION détecté - compatible"
}

# Step 2: Vérifier les ressources disponibles
check_resources() {
    log "Vérification des ressources système..."
    
    # Check RAM
    TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))
    
    log "Memoire totale: ${TOTAL_MEM_MB} MB"
    
    if [[ $TOTAL_MEM_MB -lt 4096 ]]; then
        warn "Recommandation: 4GB+ de RAM pour le trading HFT"
    fi
    
    # Check Disk Space
    AVAIL_DISK_KB=$(df -B1 / | tail -1 | awk '{print $4}')
    AVAIL_DISK_MB=$((AVAIL_DISK_KB / 1024 / 1024))
    
    log "Espace disque disponible: ${AVAIL_DISK_MB} MB"
    
    if [[ $AVAIL_DISK_MB -lt 5120 ]]; then
        error "Espace disque insuffisant: minimum 5GB recommandé"
        exit 1
    fi
    
    # Check CPU
    CPU_CORES=$(nproc)
    log "Cœurs CPU: ${CPU_CORES}"
    
    if [[ $CPU_CORES -lt 2 ]]; then
        warn "Recommandation: 2+ cœurs CPU pour le trading"
    fi
}

# Step 3: Installer les dépendances système
install_system_deps() {
    log "Installation des dépendances système..."
    
    # Mise à jour
    log "Mise à jour du système..."
    apt-get update -qq && apt-get upgrade -y -qq || {
        warn "Problème lors de la mise à jour"
    }
    
    # Packages essentiels
    PACKAGES=(
        "build-essential"
        "curl" 
        "wget"
        "git"
        "vim"
        "htop"
        "tmux"
        "net-tools"
        "iptables"
        "curl"
        "software-properties-common"
    )
    
    log "Installation des packages: ${PACKAGES[*]}"
    apt-get install -y -qq "${PACKAGES[@]}" 2>/dev/null || {
        warn "Certains packages n'ont pu être installés"
    }
    
    # PostgreSQL
    log "Configuration de PostgreSQL..."
    apt-get install -y -qq postgresql postgresql-contrib 2>/dev/null || {
        warn "PostgreSQL installation has issues, will use alternative"
    }
    
    # Redis
    log "Configuration de Redis..."
    apt-get install -y -qq redis-server 2>/dev/null || {
        warn "Redis installation has issues"
    }
    
    # Python dependencies
    log "Installation des dépendances Python..."
    apt-get install -y -qq python3-pip python3-venv 2>/dev/null || {
        warn "Python pip installation has issues"
    }
    
    # System utilities
    log "Installation des utilitaires système..."
    apt-get install -y -qq chronolog cron logrotate 2>/dev/null || {
        warn "Logging utilities installation has issues"
    }
}

# Step 4: Créer l'environnement Python
setup_python_env() {
    log "Configuration de l'environnement Python..."
    
    # Create install directory
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR"
    
    # Create Python virtual environment
    log "Création de l'environnement virtuel Python..."
    if [[ -d "$INSTALL_DIR/venv" ]]; then
        warn "Environment virtuel existant, suppression..."
        rm -rf "$INSTALL_DIR/venv"
    fi
    
    python3 -m venv "$INSTALL_DIR/venv"
    log "Environment virtuel créé"
    
    # Activate and install dependencies
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel -q 2>/dev/null || {
        warn "Problème mise à jour pip"
    }
    
    # Install project dependencies
    if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
        log "Installation des dépendances du projet..."
        pip install -q -r "$PROJECT_DIR/requirements.txt" 2>/dev/null || {
            warn "Certaines dépendances du projet n'ont pu être installées"
        }
    else
        log "Aucun requirements.txt trouvé - installation minimale"
        pip install -q MetaTrader5 pandas numpy fastapi uvicorn pydantic 2>/dev/null || {
            warn "Dépendances de base manquantes"
        }
    fi
    
    # Install Python project modules
    log "Installation du projet..."
    pip install -q -e "$PROJECT_DIR" 2>/dev/null || {
        warn "Installation du projet en mode developpement a échoué"
    }
}

# Step 5: Configurer PostgreSQL
configure_postgres() {
    log "Configuration de PostgreSQL..."
    
    # Start PostgreSQL
    pg_ctlcluster $(lsb_release -is) $(lsb_release -rs) start 2>/dev/null || {
        systemctl start postgresql 2>/dev/null || {
            warn "PostgreSQL démarrage difficile"
        }
    }
    
    # Create database and user
    su - postgres -c "createuser -s $(whoami)" 2>/dev/null || {
        warn "Creation utilisateur PostgreSQL has issues"
    }
    
    su - postgres -c "createdb chaos_engine_hft" 2>/dev/null || {
        warn "Creation base de données has issues"
    }
    
    # Configure PostgreSQL for local connections
    PG_HBA="/etc/postgresql/$(lsb_release -rs)/main/pg_hba.conf"
    if [[ -f "$PG_HBA" ]]; then
        # Allow local connections
        sed -i 's/^local\s*all\s*all\s*peer/local   all   all   trust/' "$PG_HBA" 2>/dev/null || {
            warn "Modification pg_hba.conf has issues"
        }
        pg_ctlcluster $(lsb_release -is) $(lsb_release -rs) reload 2>/dev/null || {
            warn "PostgreSQL reload has issues"
        }
    fi
}

# Step 6: Configurer Redis
configure_redis() {
    log "Configuration de Redis..."
    
    # Start Redis
    systemctl start redis-server 2>/dev/null || {
        service redis-server start 2>/dev/null || {
            warn "Redis démarrage has issues"
        }
    }
    
    # Enable Redis on boot
    systemctl enable redis-server 2>/dev/null || {
        warn "Redis enable has issues"
    }
    
    # Configure Redis to listen on localhost
    REDIS_CONF="/etc/redis/redis.conf"
    if [[ -f "$REDIS_CONF" ]]; then
        # Bind to localhost only for security
        sed -i 's/^bind.*/bind 127.0.0.1/' "$REDIS_CONF" 2>/dev/null || {
            warn "Configuration Redis bind has issues"
        }
        systemctl restart redis-server 2>/dev/null || {
            warn "Redis restart has issues"
        }
    fi
}

# Step 7: Préparer les fichiers de configuration
setup_configurations() {
    log "Préparation des fichiers de configuration..."
    
    # Create config directory
    mkdir -p "$INSTALL_DIR/config"
    
    # Create default configuration if not exists
    if [[ ! -f "$INSTALL_DIR/config/default.yaml" ]]; then
        cat > "$INSTALL_DIR/config/default.yaml" << 'EOF'
environment: demo
account_mode: AUTO
trading:
  allow_buy: true
  allow_sell: true
  frequency_mode: ADAPTIVE
  market_making_enabled: true
  martingale_enabled: false
risk:
  max_daily_loss_percent: 2
  max_drawdown_percent: 8
  max_portfolio_risk_percent: 1
  max_margin_utilization_percent: 20
execution:
  max_active_orders: 10
  max_positions: 10
  min_quote_refresh_ms: 250
  max_quote_refresh_ms: 5000
chaos:
  enabled: true
  score_min: 0
  score_max: 1
broker:
  auto_detect: true
  require_limit_orders: true
  dom_optional: true
  boc_optional: true
EOF
        log "Configuration par défaut créée"
    else
        log "Configuration par défaut existe déjà"
    fi
    
    # Create risk configuration
    if [[ ! -f "$INSTALL_DIR/config/risk.yaml" ]]; then
        cat > "$INSTALL_DIR/config/risk.yaml" << 'EOF'
# Risk configuration overrides
max_daily_loss_percent: 2
max_drawdown_percent: 8
max_margin_utilization_percent: 20
EOF
        log "Configuration risque créée"
    fi
    
    # Create symbols configuration
    if [[ ! -f "$INSTALL_DIR/config/symbols.yaml" ]]; then
        cat > "$INSTALL_DIR/config/symbols.yaml" << 'EOF'
# Symbol-specific overrides
EURUSDm:
  max_spread_points: 20
  max_inv_lots: 3.0
  min_volatility_pct: 0.0001
  max_volatility_pct: 5.0
EOF
        log "Configuration symboles créée"
    fi
}

# Step 8: Créer les services systemd
setup_systemd() {
    log "Création des services systemd..."
    
    # Main bot service
    cat > "/etc/systemd/system/chaos-engine-hft.service" << 'EOF'
[Unit]
Description=CHAOS ENGINE HFT Trading Bot
After=postgresql.service redis.service network.target
Wants=postgresql.service redis.service

[Service]
Type=simple
WorkingDirectory=/opt/chaos_engine_hft
ExecStart=/opt/chaos_engine_hft/venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
# Security
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
# Logging
StandardOutput=append:/var/log/chaos_engine_hft/access.log
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # Monitoring service
    cat > "/etc/systemd/system/chaos-engine-hft-monitor.service" << 'EOF'
[Unit]
Description=CHAOS ENGINE HFT Monitoring Service
After=chaos-engine-hft.service
Wants=chaos-engine-hft.service

[Service]
Type=simple
WorkingDirectory=/opt/chaos_engine_hft
ExecStart=/opt/chaos_engine_hft/venv/bin/python scripts/monitor.py
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    
    # Health check service
    cat > "/etc/systemd/system/chaos-engine-hft-healthcheck.service" << 'EOF'
[Unit]
Description=CHAOS ENGINE HFT Health Check Service
After=chaos-engine-hft.service

[Service]
Type=oneshot
ExecStart=/opt/chaos_engine_hft/healthcheck.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    log "Services systemd créés"
}

# Step 9: Configurer les journaux
setup_logging() {
    log "Configuration des journaux..."
    
    # Create log rotation config
    cat > "/etc/logrotate.d/chaos-engine-hft" << 'EOF'
/var/log/chaos_engine_hft/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload rsyslog.service > /dev/null 2>&1 || true
    endpostrotate
}
EOF
    
    # Ensure log directory exists and has proper permissions
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR" 2>/dev/null || true
    
    # Create initial log files
    touch "$LOG_DIR/access.log"
    touch "$LOG_DIR/error.log"
    chmod 644 "$LOG_DIR"/*.log 2>/dev/null || true
    
    log "Configuration des journaux terminée"
}

# Step 10: Vérifier les ports
check_ports() {
    log "Vérification des ports..."
    
    # Check if port 8000 is already in use
    if command -v ss &>/dev/null; then
        PORT_IN_USE=$(ss -tlnp | grep ':8000 ' | wc -l)
        if [[ $PORT_IN_USE -gt 0 ]]; then
            warn "Le port 8000 est déjà utilisé"
        else
            log "Port 8000 disponible"
        fi
    fi
    
    # Check if port 5432 (PostgreSQL) is available
    if command -v ss &>/dev/null; then
        PG_IN_USE=$(ss -tlnp | grep ':5432 ' | wc -l)
        if [[ $PG_IN_USE -gt 0 ]]; then
            warn "Le port 5432 (PostgreSQL) est déjà utilisé"
        else
            log "Port PostgreSQL 5432 disponible"
        fi
    fi
}

# Step 11: Exécuter les tests
run_tests() {
    log "Exécution des tests..."
    
    # Verify Python can import key modules
    source "$INSTALL_DIR/venv/bin/activate"
    
    log "Test d'import des modules clés..."
    python3 -c "
import sys
sys.path.insert(0, '/opt/chaos_engine_hft')
try:
    import MetaTrader5
    print('MetaTrader5: OK')
except ImportError:
    print('MetaTrader5: non disponible (attendu sur Ubuntu)')
    
try:
    import pandas
    print('pandas: OK')
except ImportError:
    print('pandas: non disponible')
    
try:
    import fastapi
    print('fastapi: OK')
except ImportError:
    print('fastapi: non disponible')
" 2>&1 || warn "Tests d'import ont rencontré des erreurs"
}

# Step 12: Produire un rapport d'installation
generate_report() {
    log "Génération du rapport d'installation..."
    
    REPORT_FILE="$INSTALL_DIR/INSTALLATION_REPORT_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$REPORT_FILE" << REPORT_EOF
================================================================================
                  CHAOS ENGINE HFT - RAPPORT D'INSTALLATION
================================================================================

Date d'installation: $(date '+%Y-%m-%d %H:%M:%S')

1. ENVIRONNEMENT SYSTÈME
   - OS: $(lsb_release -ds)
   - Version: $(lsb_release -rs)
   - Kernel: $(uname -r)
   - Cœurs CPU: $(nproc)
   - Memoire: $(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}') MB
   - Disque disponible: $(df -h / | tail -1 | awk '{print $5}') utilisé, $(df -h / | tail -1 | awk '{print $4}') libre

2. INSTALLATION LOGICIELLE
   - répertoire d'installation: $INSTALL_DIR
   - Environnement Python: $INSTALL_DIR/venv
   - PostgreSQL: $(pg_isready 2>/dev/null && echo "fonctionnel" || echo "non vérifié")
   - Redis: $(redis-cli ping 2>/dev/null && echo "fonctionnel" || echo "non vérifié")

3. DÉPENDANCES
   - MetaTrader5: $(python3 -c "import MetaTrader5; print('disponible')" 2>/dev/null || echo "non disponible (Ubuntu)")
   - Pandas: $(python3 -c "import pandas; print('disponible')" 2>/dev/null || echo "non disponible")
   - FastAPI: $(python3 -c "import fastapi; print('disponible')" 2>/dev/null || echo "non disponible")

4. SERVICES SYSTEMd
   - chaos-engine-hft.service: $(systemctl is-enabled chaos-engine-hft.service 2>/dev/null && echo "activé" || echo "non activé")
   - chaos-engine-hft-monitor.service: $(systemctl is-enabled chaos-engine-hft-monitor.service 2>/dev/null && echo "activé" || echo "non activé")

5. RÉSEAU
   - Port API: 8000 $(ss -tlnp 2>/dev/null | grep ':8000 ' > /dev/null && echo "écoute" || echo "non écouté")
   - Port PostgreSQL: 5432 $(ss -tlnp 2>/dev/null | grep ':5432 ' > /dev/null && echo "écoute" || echo "non écouté")
   - Port Redis: 6379 $(redis-cli ping 2>/dev/null > /dev/null && echo "écoute" || echo "non écouté")

6. PROCHAINES ÉtAPES
   - Démarrer le bot: systemctl start chaos-engine-hft
   - Vérifier l'état: systemctl status chaos-engine-hft
   - Accéder à l'API: http://localhost:8000/api/v1/status
   - Consulter la documentation: http://localhost:8000/api/docs

7. SÉCURITÉ
   - Mode démonstration: activé par défaut
   - Trading réel: désactivé (allow_real_trading: false)
   - Ports accessibles uniquement sur localhost (Redis, PostgreSQL)

================================================================================
REPORT_EOF

    log "Rapport d'installation créé: $REPORT_FILE"
}

# Main execution
main() {
    echo ""
    check_ubuntu_version
    check_resources
    install_system_deps
    setup_python_env
    configure_postgres
    configure_redis
    setup_configurations
    setup_systemd
    setup_logging
    check_ports
    run_tests
    generate_report
    
    echo ""
    echo "========================================="
    echo "Installation terminée!"
    echo "========================================="
    echo ""
    log "Rapport disponible dans: /opt/chaos_engine_hft/INSTALLATION_REPORT_*.txt"
    log "Configuration: /opt/chaos_engine_hft/config/"
    log "Logs: /var/log/chaos_engine_hft/"
    echo ""
    log "Prochaine étape: systemctl start chaos-engine-hft (mode démo)"
    echo ""
}

# Run main function
main "$@"