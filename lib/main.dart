import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'api_service.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CrisisCloud',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
      ),
      home: const MyHomePage(title: 'CrisisCloud Locations'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  final ApiService apiService = ApiService();
  List<Location> locations = [];
  bool isLoading = true;

  late GoogleMapController mapController;

  // Center on Norfolk, VA
  final CameraPosition initialCameraPosition = const CameraPosition(
    target: LatLng(36.8508, -76.2859),
    zoom: 12,
  );

  @override
  void initState() {
    super.initState();
    fetchLocations();
  }

  Future<void> fetchLocations() async {
    try {
      final data = await apiService.getLocations();
      setState(() {
        locations = data;
        isLoading = false;
      });
    } catch (e) {
      print('Error fetching locations: $e');
      setState(() {
        isLoading = false;
      });
    }
  }

  Set<Marker> getMarkers() {
    return locations
        .map(
          (loc) => Marker(
            markerId: MarkerId('${loc.lat},${loc.lng}'),
            position: LatLng(loc.lat, loc.lng),
          ),
        )
        .toSet();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : GoogleMap(
              initialCameraPosition: initialCameraPosition,
              markers: getMarkers(),
              onMapCreated: (controller) => mapController = controller,
            ),
    );
  }
}
