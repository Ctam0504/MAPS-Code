#define MINUNIT_IMPLEMENTATION
#include "minunit.h"
#include <string.h>
#include "minunit.h"
#include "include/weather_station.h"
#include "include/weather_types.h"

MU_TEST(test_station_init) {
    WeatherStation station;
    station_init(&station);
    mu_assert_int_eq(0, station.num_callbacks);
}

MU_TEST(test_station_register) {
    WeatherStation station;
    station_init(&station);
    station_register(&station, phone_display_update);
    mu_assert_int_eq(1, station.num_callbacks);
}

MU_TEST(test_station_notify_standard_data) {
    WeatherStation station;
    station_init(&station);
    station_register(&station, phone_display_update);
    station_register(&station, window_display_update);

    WeatherData data = {25.0, 60.0};
    station_notify(&station, &data);
    // Expected output: Phone Display: Temperature = 25.00°C, Humidity = 60.00%
    //                  Window Display: Temperature = 25.00°C, Humidity = 60.00%
}

MU_TEST(test_station_notify_error_data) {
    WeatherStation station;
    station_init(&station);
    station_register(&station, phone_display_update);
    station_register(&station, window_display_update);

    WeatherData error_data = {-10.0, 60.0};
    station_notify(&station, &error_data);
    // Expected output: Phone Display: Temperature = -10.00°C, Humidity = 60.00%
    //                  Window Display: Temperature = -10.00°C, Humidity = 60.00%
}

MU_TEST_SUITE(test_suite) {
    MU_RUN_TEST(test_station_init);
    MU_RUN_TEST(test_station_register);
    MU_RUN_TEST(test_station_notify_standard_data);
    MU_RUN_TEST(test_station_notify_error_data);
}

MU_RUN_SUITE(test_suite)