import model.LightDevice;
import command.LightOnCommand;
import command.LightOffCommand;
import invoker.RemoteControl;
import exception.CommandException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TestHarness {
    @Test
    void testLightOnCommand() {
        LightDevice lightDevice = new LightDevice();
        LightOnCommand lightOnCommand = new LightOnCommand(lightDevice);
        lightOnCommand.execute();
        assertTrue(lightDevice.isOn(), "Light should be on");
    }

    @Test
    void testLightOffCommand() {
        LightDevice lightDevice = new LightDevice();
        lightDevice.turnOn();
        LightOffCommand lightOffCommand = new LightOffCommand(lightDevice);
        lightOffCommand.execute();
        assertFalse(lightDevice.isOn(), "Light should be off");
    }

    @Test
    void testLightOffCommandWhenOff() {
        LightDevice lightDevice = new LightDevice();
        LightOffCommand lightOffCommand = new LightOffCommand(lightDevice);
        assertThrows(CommandException.class, () -> lightOffCommand.execute(), "CommandException expected");
    }

    @Test
    void testLightOnCommandWithBrightness() {
        LightDevice lightDevice = new LightDevice();
        lightDevice.setBrightness(50);
        LightOnCommand lightOnCommand = new LightOnCommand(lightDevice);
        lightOnCommand.execute();
        assertTrue(lightDevice.isOn(), "Light should be on");
        assertEquals(50, lightDevice.getBrightness(), "Brightness should be 50");
    }

    @Test
    void testUndoLightOnCommand() {
        LightDevice lightDevice = new LightDevice();
        RemoteControl remoteControl = new RemoteControl(1);
        LightOnCommand lightOnCommand = new LightOnCommand(lightDevice);
        remoteControl.setCommand(0, lightOnCommand);
        remoteControl.pressButton(0);
        remoteControl.pressUndoButton();
        assertFalse(lightDevice.isOn(), "Light should be off after undo");
    }

    @Test
    void testUndoLightOffCommand() {
        LightDevice lightDevice = new LightDevice();
        lightDevice.turnOn();
        RemoteControl remoteControl = new RemoteControl(1);
        LightOffCommand lightOffCommand = new LightOffCommand(lightDevice);
        remoteControl.setCommand(0, lightOffCommand);
        remoteControl.pressButton(0);
        remoteControl.pressUndoButton();
        assertTrue(lightDevice.isOn(), "Light should be on after undo");
    }

    @Test
    void testUndoLightOffCommandWhenOff() {
        LightDevice lightDevice = new LightDevice();
        RemoteControl remoteControl = new RemoteControl(1);
        LightOffCommand lightOffCommand = new LightOffCommand(lightDevice);
        remoteControl.setCommand(0, lightOffCommand);
        remoteControl.pressUndoButton();
        assertFalse(lightDevice.isOn(), "Light should be off after undo");
    }

    @Test
    void testMainMethod() {
        try {
            Main.main(new String[0]);
        } catch (Exception e) {
            fail("Main method should not throw exception: " + e.getMessage());
        }
    }
}