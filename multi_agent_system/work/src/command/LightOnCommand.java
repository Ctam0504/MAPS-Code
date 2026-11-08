package command;

import model.LightDevice;
import exception.CommandException;

public class LightOnCommand implements ICommand {
    LightDevice lightDevice;

    public LightOnCommand(LightDevice lightDevice) {
        this.lightDevice = lightDevice;
    }

    @Override
    public void execute() throws CommandException {
        lightDevice.turnOn();
    }

    @Override
    public void undo() {
        lightDevice.turnOff();
    }
}