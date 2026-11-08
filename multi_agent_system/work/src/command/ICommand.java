package command;

public interface ICommand {
    void execute() throws CommandException;
    void undo();
}