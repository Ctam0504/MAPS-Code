#include "include/event_bus.h"
#include "include/event_listener.h"
#include "include/order_types.h"
#include <stdlib.h>

void bus_init(EventBus* bus) {
    bus->listener_count = 0;
}

int bus_register(EventBus* bus, EventListenerCallback callback) {
    if (bus->listener_count >= MAX_LISTENERS) {
        return -1;
    }
    bus->callbacks[bus->listener_count++] = callback;
    return 0;
}

int bus_publish(EventBus* bus, const OrderEvent* event, EventError* error) {
    for (int i = 0; i < bus->listener_count; i++) {
        if (bus->callbacks[i](event, error) != 0) {
            return -1;
        }
    }
    return 0;
}