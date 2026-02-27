# Azure VM GPU Setup — Successful Workflow

**VM Specification:** NV36ads A10 v5 (NVIDIA A10-24Q vGPU, Ubuntu 22.04)
**Date:** February 27, 2026

This document outlines the exact steps that successfully installed the NVIDIA drivers and enabled Docker GPU passthrough on this Azure VM, overcoming issues with Secure Boot and standard retail PCI drivers not recognizing the Azure vGPU partition.

---

## 1. Prerequisite: Disable Secure Boot
Installing custom / third-party drivers on Azure Ubuntu VMs with Secure Boot enabled via an SSH Bastion connection is not feasible due to the inability to interact with the interactive MOK (Machine Owner Key) enrollment screen at boot.

**Action Taken:**
The Azure Administrator disabled UEFI Secure Boot at the VM property level via the Azure Portal/CLI. This allowed unsigned (or custom DKMS locally-compiled) kernel modules to load without being rejected.

---

## 2. Purge Existing / Broken NVIDIA Packages
To ensure a clean slate, all failed attempts with standard Ubuntu `nvidia-driver` packages were removed.

**Action Taken:**
```bash
sudo apt-get purge -y '*nvidia*'
sudo apt-autoremove -y
```

---

## 3. Install Azure-Specific GRID vGPU Driver
Standard NVIDIA retail/server drivers will return `No such device` upon `modprobe` because Azure presents an A10-24Q **vGPU** (virtual partitioned GPU), not a direct PCIe passthrough. The official Microsoft/NVIDIA GRID driver script is required.

**Action Taken:**
```bash
sudo apt-get update
sudo apt-get install -y build-essential dkms pkg-config
wget -O grid.run "https://go.microsoft.com/fwlink/?linkid=874272"
sudo chmod +x grid.run
sudo ./grid.run -s --dkms
```
*(Result: Installed driver version `550.144.06` for CUDA 12.4)*

---

## 4. Install Docker Compose (Standalone)
The `docker-compose-plugin` package was unavailable in the locked-down Azure repos.

**Action Taken:**
Installed the binary directly:
```bash
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/bin/docker-compose
sudo chmod +x /usr/bin/docker-compose
```

---

## 5. Enable Docker GPU Passthrough (NVIDIA Container Toolkit)
The toolkit intercepts Docker container creation to mount the host GPU drivers.

**Action Taken:**
```bash
# Add repo
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker daemon & restart
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 6. Verification
The final test confirmed that Docker successfully bridged the A10 vGPU into a containerized environment.

**Command Run:**
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

**Result:**
```text
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.144.06             Driver Version: 550.144.06     CUDA Version: 12.4     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA A10-24Q                 On  |   00000002:00:00.0 Off |                    0 |
| N/A   N/A    P0             N/A /  N/A  |       1MiB /  24512MiB |      0%      Default |
+-----------------------------------------+------------------------+----------------------+
```

**Phase 1 Complete.**
