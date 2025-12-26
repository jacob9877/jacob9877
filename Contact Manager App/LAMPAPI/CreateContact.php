<?php

// Function to get the request data from the JSON input
function getRequestInfo()
{
    return json_decode(file_get_contents('php://input'), true);
}

// Function to send the result back to the client as JSON
function sendResultInfoAsJson($obj)
{
    header('Content-type: application/json');
    echo $obj;
}

// Function to return an error message with a default ID of 0
function returnWithError($err)
{
    $retValue = '{"id":0,"error":"' . $err . '"}';
    sendResultInfoAsJson($retValue);
}

// Function to return success message with the contact ID
function returnWithInfo($id)
{
    $retValue = '{"id":' . $id . ',"error":""}';
    sendResultInfoAsJson($retValue);
}

// Get the input data from the request
$inData = getRequestInfo();

// Trim whitespace from the name field
$name = trim($inData["name"]);

// If the name is empty, return an error
if (empty($name)) {
    returnWithError("Name cannot be empty");
    exit();
}

// Connect to the MySQL database
$conn = new mysqli("localhost", "TheBeast", "WeLoveCOP4331", "COP4331");

// Check for connection errors
if( $conn->connect_error )
{
    returnWithError( $conn->connect_error );
}
else
{
    // Check if a contact with the same phone number or email already exists for this user
    $stmt = $conn->prepare("SELECT * FROM Contacts WHERE (Phone = ? OR Email = ?) AND UserID = ?");
    $stmt->bind_param("ssi", $inData["phone"], $inData["email"], $inData["userId"]);
    $stmt->execute();
    $result = $stmt->get_result();

    // If a duplicate is found, return an error
    if ($result->num_rows > 0) 
    {
        returnWithError("A contact with this phone number or email already exists for this user");
        $stmt->close();
        $conn->close();
        exit();
    }
    $stmt->close();
    
    // Get the next sequential userId
    $stmt = $conn->prepare("SELECT MAX(UserID) as maxUserId FROM Contacts");
    $stmt->execute();
    $result = $stmt->get_result();
    $row = $result->fetch_assoc();
    $nextUserId = ($row['maxUserId'] !== null) ? $row['maxUserId'] + 1 : 1; // Increment the max userId by 1
    $stmt->close();

    $userId = $inData["userId"];

    $dateCreated = date("Y-m-d H:i:s"); // Get current date and time
    $stmt = $conn->prepare("INSERT INTO Contacts (UserID, Name, Phone, Email, DateCreated) VALUES (?, ?, ?, ?, ?)");
    $stmt->bind_param("issss", $userId, $name, $inData["phone"], $inData["email"], $dateCreated);

    $stmt->execute();

    // If the insert is successful, return the contact ID
    if ($stmt->affected_rows > 0)
    {
        $id = $stmt->insert_id;
        returnWithInfo($id); // Return the new contact ID
    }
    else
    {
        returnWithError("Error Creating Contact");
    }

    // Close the statement and connection
    $stmt->close();
    $conn->close();
}

?>
