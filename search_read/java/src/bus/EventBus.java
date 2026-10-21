package bus;

import event.OrderEvent;
import listener.IOrderEventListener;
import java.util.ArrayList;
import java.util.List;

public class EventBus {
    private List<IOrderEventListener> listeners;

    public EventBus() {
        this.listeners = new ArrayList<>();
    }

    public void registerListener(IOrderEventListener listener) {
        listeners.add(listener);
    }

    public void unregisterListener(IOrderEventListener listener) {
        listeners.remove(listener);
    }

    public void publishEvent(OrderEvent event) {
        for (IOrderEventListener listener : listeners) {
            try {
                listener.onEvent(event);
            } catch (EventProcessingException e) {
                // Handle exception if needed
            }
        }
    }
}