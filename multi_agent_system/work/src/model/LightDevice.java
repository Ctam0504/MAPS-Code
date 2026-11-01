package model;

import exception.CommandException;

public class LightDevice {
    boolean isOn;
    int brightness;

    public LightDevice() {
        this.isOn = false;
        this.brightness = 0;
    }

    public void turnOn() {
        this.isOn = true;
    }

    public void turnOff() {
        this.isOn = false;
    }

    public boolean isOn() {
        return isOn;
    }

    public int getBrightness() {
        return brightness;
    }

    public void setBrightness(int brightness) throws CommandException {
        if (!this.isOn) {
            throw new CommandException("Cannot set brightness when light is off");
        }
        this.brightness = brightness;
    }
}