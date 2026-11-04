#!/usr/bin/env bash
#
# CHAOS ENGINE HFT - Start Script
# Démarre le bot en mode démonstration
#

set -euo pipefail

PROJECT_DIR="/c/Users/Gryphen/Downloads/hft_bot"
INSTALL_DIR="/opt/chaos_engine_hft"
LOG_DIR="/var/log/chaos_engine_hft"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[START]${NC} $1"
}

log "Démarrage de CHAOS ENGINE HFT en mode démonstration..."

# Vérifier que l'environnement virtuel existe
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    error "Environment virtuel non trouvé: $INSTALL_DIR/venv"
    log "Exécutez d'abord install.sh"
    exit 1
fi

# Vérifier la configuration
if [[ ! -f "$INSTALL_DIR/config/default.yaml" ]]; then
    warn "Configuration par défaut introuvable"
fi

# Démarrer le service systemd (API)
log "Démarrage du service API..."
systemctl start chaos-engine-hft.service

# Attendre que le service soit prêt
log "Attente du démarrage du service..."
for i in $(seq 1 30); do
    if systemctl is-active --quiet chaos-engine-hft.service 2>/dev/null; then
        log "Service API démarré avec succès"
        break
    fi
    sleep 1
done

# Vérifier le statut
STATUS=$(systemctl is-active chaos-engine-hft.service 2>/dev/null || echo "inactive")
if [[ "$STATUS" == "active" ]]; then
    log "CHAOS ENGINE HFT API is running on port 8000"
    log "Documentation API: http://localhost:8000/api/docs"
    log "Health check: http://localhost:8000/health"
else
    warn "Le service API n'a pas démarré correctement"
    log "Vérifier les logs: journalctl -u chaos-engine-hft.service -f"
fi

# Démarrer le service de monitoring (optionnel)
log "Démarrage du service de monitoring..."
systemctl start chaos-engine-hft-monitor.service 2>/dev/null || {
    warn "Service de monitoring non disponible ou échec du démarrage"
}

log "CHAOS ENGINE HFT est prêt en mode démonstration"
log "Aucun trading réel n'est effectué automatiquement"
log "Utilisez l'API: POST /api/v1/bot/start (démo) ou configuration manuelle"