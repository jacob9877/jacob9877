<?php
  header('Content-Type: application/json');
  
  // Database connection parameters
  $servername = "localhost";
  $username = "TheBeast";
  $password = "WeLoveCOP4331";
  $dbname = "COP4331";

  // Create connection
  $conn = new mysqli($servername, $username, $password, $dbname);

  // Check connection
  if ($conn->connect_error) {
      die(json_encode(['message' => 'Connection failed: ' . $conn->connect_error]));
  }

  // Retrieve the ID from GET request
  $id = $_GET['id'];

  // Get the data from the request body
  $data = json_decode(file_get_contents('php://input'), true);
  $name = $data['name'];
  $phone = $data['phone'];
  $email = $data['email'];

  // Prepare and execute the SQL statement
  $stmt = $conn->prepare("UPDATE Contacts SET Name = ?, Phone = ?, Email = ? WHERE ID = ?");
  $stmt->bind_param("sssi", $name, $phone, $email, $id);

  // Execute the statement and check if successful
  if ($stmt->execute()) {
      echo json_encode(['message' => 'Contact updated successfully']);
  } else {
      echo json_encode(['message' => 'Failed to update contact']);
  }

  // Close the statement and connection
  $stmt->close();
  $conn->close();
?>
