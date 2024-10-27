#!/usr/bin/bash

# Prepare system
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install git ruby -y

# Clone this repo
git clone https://github.com/oermenz/midihub
cd midihub

# Optimize for power efficiency and fast boot
sudo cp config.txt /boot/
sudo cp cmdline.txt /boot/

# Make device identifiable more easily on the network
sudo apt-get install avahi-daemon -y

# Install MIDI autoconnect script
sudo cp connectall.rb /usr/local/bin/
sudo chmod +x /usr/local/bin/connectall.rb
sudo cp 33-midiusb.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo service udev restart
sudo cp midi.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable midi.service
sudo systemctl start midi.service

# FW for older Midisport devices
sudo apt-get install midisport-firmware -y

# Bluez for Python3
sudo apt install python3-bluez

# Setup MIDI bluetooth
git clone https://github.com/oxesoft/bluez
sudo apt-get install -y autotools-dev libtool autoconf
sudo apt-get install -y libasound2-dev
sudo apt-get install -y libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev
cd bluez
./bootstrap
./configure --enable-midi --prefix=/usr --mandir=/usr/share/man --sysconfdir=/etc --localstatedir=/var
make
sudo make install
cd ..
sudo cp 44-bt.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo service udev restart
sudo cp btmidi.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable btmidi.service
sudo systemctl start btmidi.service

# Setup OLED screem
sudo usermod -a -G i2c,spi,gpio oermens
sudo apt install python3-dev python3-pip python3-numpy libfreetype6-dev libjpeg-dev build-essential
sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev
sudo apt install fonts-lato
sudo cp midioled.py /usr/local/bin/
sudo chmod a+x /usr/local/bin/midioled.py

# Create alias to show connected devices
echo >> ~/.bashrc
echo "alias midi='aconnect -l'" >> ~/.bashrc
echo >> ~/.bashrc

# Create alias to reconnect devices
echo >> ~/.bashrc
echo "alias connect='connectall.rb'" >> ~/.bashrc
echo >> ~/.bashrc

# Make FS read-only to avoid SD card corruption
# git clone https://gitlab.com/larsfp/rpi-readonly
# cd rpi-readonly
# sudo ./setup.sh -y
# cd ..

# Turn on read-only mode
# ro
# Use command "rw" to enable writes again

# echo "The system will now reboot in read-only mode."
# echo "Use command \"rw\" to enable writes again."
read -p "Press [enter] to reboot"
sudo reboot
