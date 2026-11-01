package command;

import exception.CommandException;

public interface ICommand {
    void execute() throws CommandException;
    void undo();
}