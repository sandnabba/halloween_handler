# Changelog

## 2026

Home Assistant reinstalled from scratch; the flicker light is now `light.fasadbelysning_ytterbelysning_entre`.

* Debug mode: the whole scenario runs, but no calls are sent to Home Assistant
* Old Flask dashboard on port 5000 removed; the React frontend is the only UI
* ha_controller refactored: shared `SystemState`, one trigger check, plain REST calls to Home Assistant (`homeassistant-api` dropped), paho-mqtt 2 callbacks

## 2025

Major update. First publish to GitHub.

* Web frontend (new)
* LED portal (new)
* Major rewrite of ha_controller

## 2024

Major rewrite in Home Assistant. Move from `ha-plejd` to `hass-plejd`.

## 2023

Change of camera NVR. Move to MQTT-based auto activation of scenario.  

Creation of the [**`zombie_sensor`**](https://github.com/sandnabba/zombie_sensor).

## 2021-2022

First version. Basically a single script listening for events over a pipe from Zoneminder (NVR), triggering some events + flickering in Home Assistant using `ha-plejd`.