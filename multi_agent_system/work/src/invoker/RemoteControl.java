package invoker;

import command.ICommand;

public class RemoteControl {
    ICommand[] slots;
    ICommand lastCommand;

    public RemoteControl(int numberOfSlots) {
        slots = new ICommand[numberOfSlots];
    }

    public void setCommand(int slot, ICommand command) {
        slots[slot] = command;
    }

    public void pressButton(int slot) {
        if (slot < 0 || slot >= slots.length) {
            throw new IllegalArgumentException("Invalid slot number");
        }
        ICommand command = slots[slot];
        if (command != null) {
            try {
                command.execute();
                lastCommand = command;
            } catch (CommandException e) {
                System.out.println("Command execution failed: " + e.getMessage());
            }
        }
    }

    public void pressUndoButton() {
        if (lastCommand != null) {
            lastCommand.undo();
        }
    }
}