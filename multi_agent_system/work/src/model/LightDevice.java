package model;

public class LightDevice {
    boolean isOn;
    int brightness;

    public LightDevice() {
        this.isOn = false;
        this.brightness = 0;
    }

    public void turnOn() {
        this.isOn = true;
        System.out.println("Light is on.");
    }

    public void turnOff() {
        this.isOn = false;
        System.out.println("Light is off.");
    }

    public void setBrightness(int brightness) {
        if (this.isOn) {
            this.brightness = brightness;
            System.out.println("Brightness set to " + brightness);
        } else {
            throw new CommandException("Cannot set brightness when light is off.");
        }
    }

    public int getBrightness() {
        return this.brightness;
    }
}