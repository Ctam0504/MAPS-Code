package command;

import model.LightDevice;
import exception.CommandException;

public class LightOffCommand implements ICommand {
    LightDevice lightDevice;

    public LightOffCommand(LightDevice lightDevice) {
        this.lightDevice = lightDevice;
    }

    @Override
    public void execute() throws CommandException {
        if (lightDevice.isOn()) {
            lightDevice.turnOff();
        } else {
            throw new CommandException("Light is already off");
        }
    }

    @Override
    public void undo() {
        lightDevice.turnOn();
    }
}