#!/bin/bash
# Скрипт бэкапа базы данных

BACKUP_DIR="/opt/freelance-bot/backups"
DB_FILE="/opt/freelance-bot/freelance_aggregator.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_DIR/freelance_aggregator_$DATE.db"
    # Удаляем бэкапы старше 30 дней
    find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
    echo "Backup created: $BACKUP_DIR/freelance_aggregator_$DATE.db"
else
    echo "Database file not found!"
    exit 1
fi
