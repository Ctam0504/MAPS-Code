package src;

import model.LightDevice;
import command.ICommand;
import command.LightOnCommand;
import command.LightOffCommand;
import invoker.RemoteControl;
import exception.CommandException;

public class Main {
    public static void main(String[] args) {
        LightDevice lightDevice = new LightDevice();
        ICommand lightOnCommand = new LightOnCommand(lightDevice);
        ICommand lightOffCommand = new LightOffCommand(lightDevice);

        RemoteControl remoteControl = new RemoteControl(2);
        remoteControl.setCommand(0, lightOnCommand);
        remoteControl.setCommand(1, lightOffCommand);

        try {
            remoteControl.pressButton(0); // Turn on light
            System.out.println("Light is on, brightness: " + lightDevice.getBrightness());

            remoteControl.pressButton(1); // Turn off light
            System.out.println("Light is off");

            remoteControl.pressUndoButton(); // Undo turn off
            System.out.println("Light is on, brightness: " + lightDevice.getBrightness());

            remoteControl.pressUndoButton(); // Undo turn on
            System.out.println("Light is off");
        } catch (CommandException e) {
            System.err.println("CommandException: " + e.getMessage());
        }
    }
}