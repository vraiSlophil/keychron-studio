#!/usr/bin/env bash
# Enforce Keychron Studio's privilege-separation model:
# remove any udev "uaccess" rule so the keyboard's raw-HID node is ROOT-ONLY.
# The GUI then reaches it only through the pkexec-elevated helper.
# Run once (requires sudo). Re-plug the keyboard afterwards.
set -euo pipefail
RULE=/etc/udev/rules.d/50-keychron.rules
if [ -f "$RULE" ]; then
    echo "Removing user-access udev rule: $RULE"
    sudo rm -f "$RULE"
    sudo udevadm control --reload-rules && sudo udevadm trigger
    echo "Done. Unplug and replug the keyboard. The HID node is now root-only."
else
    echo "No user-access rule found ($RULE). Node is already root-only. Nothing to do."
fi
