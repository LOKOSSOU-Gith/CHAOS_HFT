#!/usr/bin/env bash
#
# CHAOS ENGINE HFT - Stop Script
# Arrête le bot de trading de façon contrôlée
#

set -euo pipefail

PROJECT_DIR="/c/Users/Gryphen/Downloads/hft_bot"
INSTALL_DIR="/opt/chaos_engine_hft"
LOG_DIR="/var/log/chaos_engine_hft"

# Colors
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${RED}[STOP]${NC} $1"
}

log "Arrêt contrôlé de CHAOS ENGINE HFT..."

# Arrêter le service de monitoring
log "Arrêt du service de monitoring..."
systemctl stop chaos-engine-hft-monitor.service 2>/dev/null || {
    warn "Service de monitoring déjà arrêté ou non actif"
}

# Arrêter le service principal
log "Arrêt du service API..."
systemctl stop chaos-engine-hft.service

# Vérifier l'arrêt
STATUS=$(systemctl is-active chaos-engine-hft.service 2>/dev/null || echo "inactive")
if [[ "$STATUS" == "inactive" ]]; then
    log "CHAOS ENGINE HFT arrêté avec succès"
else
    warn "Le service s'arrête difficilement"
    log "Forçage d'arrêt..."
    systemctl kill chaos-engine-hft.service 2>/dev/null || true
fi

# Journaliser l'arrêt
log "CHAOS ENGINE HFT arrêté - aucune position en cours ne sera clôturée automatiquement"
log "Pour un arrêt d'urgence, utilisez les commandes MQL5 directement"
log "Consultez les logs: journalctl -u chaos-engine-hft.service --since '1 hour ago'"