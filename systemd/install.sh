#!/usr/bin/env bash
# 一键部署脚本 (Ubuntu / systemd)
# 用法:
#   sudo bash systemd/install.sh /opt/remote-jobs your_username
# 如果不带参数，使用默认值 /opt/remote-jobs 和当前 sudo 用户
set -euo pipefail

INSTALL_DIR="${1:-/opt/remote-jobs}"
RUN_USER="${2:-$SUDO_USER}"

if [ "$EUID" -ne 0 ]; then
    echo "请用 sudo 运行: sudo bash systemd/install.sh"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "项目目录: $PROJECT_DIR"
echo "安装到  : $INSTALL_DIR"
echo "运行用户: $RUN_USER"

# 1) 拷贝项目到目标目录 (排除已有运行产物)
mkdir -p "$INSTALL_DIR"
rsync -a --delete \
    --exclude='.git' --exclude='__pycache__' \
    --exclude='jobs/' --exclude='data/' --exclude='.venv/' \
    "$PROJECT_DIR"/ "$INSTALL_DIR"/

# 2) 创建 venv 并安装依赖
sudo -u "$RUN_USER" bash -c "
    cd '$INSTALL_DIR' && \
    python3 -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install -r requirements.txt
"

# 3) 创建运行产物目录
mkdir -p "$INSTALL_DIR/jobs" "$INSTALL_DIR/data"
chown -R "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"

# 4) 准备日志目录
mkdir -p /var/log
touch /var/log/remote-jobs.log /var/log/remote-jobs.err.log
chown "$RUN_USER":"$RUN_USER" /var/log/remote-jobs.log /var/log/remote-jobs.err.log

# 5) 拷贝 systemd unit 并替换占位符
TMP_UNIT_DIR="$(mktemp -d)"
sed "s|YOUR_USERNAME|$RUN_USER|g; s|/opt/remote-jobs|$INSTALL_DIR|g" \
    "$PROJECT_DIR/systemd/remote-jobs.service" > "$TMP_UNIT_DIR/remote-jobs.service"
cp "$PROJECT_DIR/systemd/remote-jobs.timer" "$TMP_UNIT_DIR/remote-jobs.timer"

cp "$TMP_UNIT_DIR/remote-jobs.service" /etc/systemd/system/
cp "$TMP_UNIT_DIR/remote-jobs.timer" /etc/systemd/system/
rm -rf "$TMP_UNIT_DIR"

systemctl daemon-reload
systemctl enable --now remote-jobs.timer

echo
echo "===== 部署完成 ====="
echo "立即跑一次: sudo systemctl start remote-jobs.service"
echo "查看定时器: systemctl list-timers remote-jobs.timer"
echo "查看日志  : tail -f /var/log/remote-jobs.log"
echo "输出目录  : $INSTALL_DIR/jobs/"
