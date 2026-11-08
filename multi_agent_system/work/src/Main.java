package src;

import model.LightDevice;
import command.ICommand;
import invoker.RemoteControl;
import service.AutomationService;

public class Main {
    public static void main(String[] args) {
        LightDevice light = new LightDevice();
        ICommand lightOnCommand = new LightOnCommand(light);
        ICommand lightOffCommand = new LightOffCommand(light);

        RemoteControl remote = new RemoteControl(2);
        remote.setCommand(0, lightOnCommand);
        remote.setCommand(1, lightOffCommand);

        remote.pressButton(0); // Light is on.
        remote.pressButton(1); // Light is off.
        remote.pressUndoButton(); // Light is on.

        AutomationService automationService = new AutomationService();
        ICommand[] script = {lightOnCommand, lightOffCommand, lightOnCommand};
        automationService.runScript(script);
    }
}