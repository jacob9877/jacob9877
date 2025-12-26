<?php
  header('Content-Type: application/json');

  // Database connection parameters
  $servername = "localhost";
  $username = "TheBeast";
  $password = "WeLoveCOP4331";
  $dbname = "COP4331";
  
  // Creates connection
  $conn = new mysqli($servername, $username, $password, $dbname);
  
  // Checks connection
  if ($conn->connect_error) {
      die(json_encode(['message' => 'Connection failed: ' . $conn->connect_error]));
  }

  // Retrieves the ID from GET request
  $id = $_GET['id'];

  // Prepares and executes the SQL statement
  $stmt = $conn->prepare("DELETE FROM Contacts WHERE ID = ?");
  $stmt->bind_param("i", $id);

  // Executes the statement and checks if successful
  if ($stmt->execute()) {
      echo json_encode(['message' => 'Contact deleted successfully']);
  } else {
      echo json_encode(['message' => 'Failed to delete contact']);
  }

  // Closes the statement and connection
  $stmt->close();
  $conn->close();
?>
