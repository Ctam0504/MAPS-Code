#include "include/weather_station.h"
#include "include/weather_types.h"

int main() {
    WeatherStation station;
    station_init(&station);
    station_register(&station, phone_display_update);
    station_register(&station, window_display_update);

    WeatherData data = {25.0, 60.0};
    station_notify(&station, &data);

    WeatherData error_data = {-10.0, 60.0};
    station_notify(&station, &error_data);

    return 0;
}