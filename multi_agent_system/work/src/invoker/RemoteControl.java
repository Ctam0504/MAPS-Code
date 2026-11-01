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
        if (slot >= 0 && slot < slots.length) {
            slots[slot].execute();
            lastCommand = slots[slot];
        }
    }

    public void pressUndoButton() {
        if (lastCommand != null) {
            lastCommand.undo();
        }
    }
}