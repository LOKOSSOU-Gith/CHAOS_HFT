#!/usr/bin/env bash
#
# CHAOS ENGINE HFT - Restart Script
# Redémarre le bot de trading
#

set -euo pipefail

PROJECT_DIR="/c/Users/Gryphen/Downloads/hft_bot"
INSTALL_DIR="/opt/chaos_engine_hft"
LOG_DIR="/var/log/chaos_engine_hft"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[RESTART]${NC} $1"
}

log "Redémarrage de CHAOS ENGINE HFT..."

# Arrêter d'abord
log "Arrêt du service..."
systemctl stop chaos-engine-hft.service 2>/dev/null || {
    warn "Impossible d'arrêter le service"
}

# Petit délai pour le nettoyage
log "Attente du nettoyage..."
sleep 2

# Redémarrer
log "Démarrage du service..."
systemctl start chaos-engine-hft.service

# Vérifier le statut
STATUS=$(systemctl is-active chaos-engine-hft.service 2>/dev/null || echo "inactive")
if [[ "$STATUS" == "active" ]]; then
    log "CHAOS ENGINE HFT redémarré avec succès"
    log "API disponible sur: http://localhost:8000"
    log "Documentation: http://localhost:8000/api/docs"
else
    warn "Le service redémarre difficilement"
    log "Vérifier les logs: journalctl -u chaos-engine-hft.service -error"
}