#!/bin/bash

set -e

sudo apt update

echo "Installing python venv..."
sudo apt install -y python3.12-venv

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installing required Qt system libraries..."
sudo apt install -y \
  libxcb-xinerama0 libxkbcommon-x11-0 libxcb1 libxcb-keysyms1 libxcb-image0 \
  libxcb-shm0 libxcb-icccm4 libxcb-sync1 libxcb-xfixes0 libxcb-shape0 libxcb-randr0 \
  libxcb-render-util0 libxrender1 libxkbcommon0 libgl1

echo "Installing tkinter..."
sudo apt install -y python3-tk

echo "Installing required tools..."
sudo apt install -y libimage-exiftool-perl

echo "Installation complete. Run the app with:"
echo "source venv/bin/activate && python main.py"

sudo apt install ruby ruby-dev build-essential -y

sudo gem install zsteg -y

echo "Setting execute permissions for all shell scripts..."
chmod +x install.sh
chmod +x features/binwalk/v1_0/runbinwalk.sh
chmod +x features/steghide/v1_0/runsteghide.sh
chmod +x features/zsteg/v1_0/runzsteg.sh 