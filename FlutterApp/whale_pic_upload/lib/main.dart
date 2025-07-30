import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:googleapis/drive/v3.dart' as drive;
import 'package:googleapis_auth/auth_io.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

late List<CameraDescription> cameras;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  cameras = await availableCameras();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      home: AutoCaptureScreen(),
    );
  }
}

class AutoCaptureScreen extends StatefulWidget {
  const AutoCaptureScreen({super.key});

  @override
  State<AutoCaptureScreen> createState() => _AutoCaptureScreenState();
}

class _AutoCaptureScreenState extends State<AutoCaptureScreen> {
  late CameraController _controller;
  late Timer _timer;
  bool _isInitialized = false;

  final clientId = ClientId("YOUR_CLIENT_ID", "YOUR_CLIENT_SECRET");
  final scopes = [drive.DriveApi.driveFileScope];

  AuthClient? _authClient;
  drive.DriveApi? _driveApi;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _authenticateGoogleDrive();
  }

  void _initializeCamera() async {
    _controller = CameraController(cameras[0], ResolutionPreset.medium);
    await _controller.initialize();
    setState(() => _isInitialized = true);

    _timer = Timer.periodic(const Duration(seconds: 10), (timer) async {
      if (!_controller.value.isTakingPicture && _driveApi != null) {
        XFile picture = await _controller.takePicture();
        await _uploadToDrive(File(picture.path));
        await File(picture.path).delete();
      }
    });
  }

  void _authenticateGoogleDrive() async {
    await clientViaUserConsent(clientId, scopes, (url) {
      print("Please go to the following URL and grant access: $url");
    }).then((AuthClient client) {
      setState(() {
        _authClient = client;
        _driveApi = drive.DriveApi(client);
      });
    });
  }

  Future<void> _uploadToDrive(File file) async {
    var media = drive.Media(file.openRead(), await file.length());
    var driveFile = drive.File();
    driveFile.name = "photo_${DateTime.now().millisecondsSinceEpoch}.jpg";
  
    // ✅ Replace this with your actual folder ID from Google Drive
    driveFile.parents = ["1Y84j1QSei69jYSSceQQ4a7z3-fibgQMd"];
  
    await _driveApi!.files.create(driveFile, uploadMedia: media);
  }

  @override
  void dispose() {
    _timer.cancel();
    _controller.dispose();
    _authClient?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Auto Camera Upload")),
      body: _isInitialized
          ? CameraPreview(_controller)
          : const Center(child: CircularProgressIndicator()),
    );
  }
}
