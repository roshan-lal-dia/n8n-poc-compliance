# Replace <YOUR_VM_IP> with the actual public IP from Azure Portal
$vmIP = "172.206.67.83"

# Test SSH (should work)
Test-NetConnection -ComputerName $vmIP -Port 22

# Test n8n port
Test-NetConnection -ComputerName $vmIP -Port 5678

# Test HTTP (for future reverse proxy)
Test-NetConnection -ComputerName $vmIP -Port 80