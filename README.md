# Mobile Data Acquisition Unit - Publishers
This repository contains the publishers for the Picarro CRDS gas analyzer, the wind sensor and the GPS receiver. 

## Picarro Command Interface
The command interface of the Picarro can output different data and different rates. The configuration of the interface 
is done via a config located at:
```commandline
C:\Picarro\G2000\AppConfig\Config\CommandInterface\CommandInterface_CFADS.ini
```
The purpose of other ini files in the folder is not clear. In the `CommandInterface_CFADS.ini` file the `meas_source`
can be defined. This is the data stream which is used for the command interface. Two data streams seem to be available:
```
meas_source = analyze_CFADS
```
This data stream is all the data that is measured by the Picarro. Note, that not every time new data is available, that necessarily all gases have been updated. According to Picarro
support it can happen that new for example new data is available, but only the CH4 value is actually new and the CO2 and
H2O values are the same from the previous measurement. This is one reason why some Picarro customers seem to opt for the
second data stream available:
```
meas_source = SyncCFDAS
```
This stream outputs new data every 5 seconds, that has been averaged over the past 5 seconds. This ensures that all
measurements have new values. This makes sense especially in the case of a long term measurements. 

Another important setting in the config file is the `meas_label` parameter. This defines which measurements from the
data stream are forwarded to the command interface. The `meas_source` and `meas_label` parameters can also been seen in
the GUI. There you have Source 1, Source 2, etc. those are the data streams that the GUI uses for displaying. The Data 
Key 1, Data Key 2, etc. are then the measurements from the data streams that are used for displaying in the graphs. To 
see which data labels are available in the corresponding stream, just select the stream as Source in the GUI and then
have a look, which Data Keys are available in the drop-down. When using the `SyncCFADS` stream one might use the 
following data keys:
```
meas_label = CO2_dry_sync, CH4_dry_sync, H20_sync
```
When using the `analyze_CFADS` data stream one might use the following data keys:
```
meas_label = CO2_dry, CH4_dry, H20
```