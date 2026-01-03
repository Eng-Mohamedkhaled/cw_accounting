#!/bin/bash
rsync -av --progress --exclude='.git' --exclude='__pycache__/' \
/odoo/code_wave_brand /odoo/jsoor_accounting ssh.jsoor.uk:/home/azureuser/
