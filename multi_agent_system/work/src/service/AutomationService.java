package service;

import invoker.RemoteControl;
import command.ICommand;

public class AutomationService {
    RemoteControl remoteControl;

    public AutomationService(RemoteControl remoteControl) {
        this.remoteControl = remoteControl;
    }

    public void addAutomation(ICommand command) {
        // Implement logic to add automation command
    }

    public void executeAutomation() {
        // Implement logic to execute automation commands
    }
}