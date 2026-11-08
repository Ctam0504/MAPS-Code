package service;

import command.ICommand;

public class AutomationService {
    public void runScript(ICommand[] script) {
        for (ICommand command : script) {
            try {
                command.execute();
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }
}