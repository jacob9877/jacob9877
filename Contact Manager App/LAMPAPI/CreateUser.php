<?php
// Enable error reporting
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

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
    $retValue = '{"id":0,"firstName":"","lastName":"","error":"' . $err . '"}';
    sendResultInfoAsJson($retValue);
}

// Function to return success message with user ID and name
function returnWithInfo($firstName, $lastName, $id)
{
    $retValue = '{"id":' . $id . ',"firstName":"' . $firstName . '","lastName":"' . $lastName . '","error":""}';
    sendResultInfoAsJson($retValue);
}

// Get the input data from the request
$inData = getRequestInfo();

if ($inData === null) {
    returnWithError("Invalid input format");
    exit();
}

// Connect to the MySQL database
$conn = new mysqli("localhost", "TheBeast", "WeLoveCOP4331", "COP4331");

if( $conn->connect_error ) 
{
    returnWithError( $conn->connect_error );
    exit();
}

// Check if a user with the same login already exists
$stmt = $conn->prepare("SELECT * FROM Users WHERE Login = ?");
if ($stmt === false) {
    returnWithError("Error preparing SQL query");
    exit();
}
$stmt->bind_param("s", $inData["login"]);
$stmt->execute();
$result = $stmt->get_result();

// If the user exists, return an error
if ($result->num_rows > 0) 
{
    returnWithError("User with this login already exists");
    $stmt->close();
    $conn->close();
    exit();
}
$stmt->close();

// Get the next sequential user ID by finding the max userId
$stmt = $conn->prepare("SELECT MAX(ID) as maxUserId FROM Users");
if ($stmt === false) {
    returnWithError("Error preparing SQL query");
    exit();
}
$stmt->execute();
$result = $stmt->get_result();
$row = $result->fetch_assoc();
$nextUserId = ($row['maxUserId'] !== null) ? $row['maxUserId'] + 1 : 1;
$stmt->close();

// Insert the new user with the next available userId
$stmt = $conn->prepare("INSERT INTO Users (ID, FirstName, LastName, Login, Password) VALUES (?, ?, ?, ?, ?)");
if ($stmt === false) {
    returnWithError("Error preparing SQL query");
    exit();
}
$stmt->bind_param("issss", $nextUserId, $inData["firstName"], $inData["lastName"], $inData["login"], $inData["password"]);
$stmt->execute();

// If the insert is successful, return the user information
if ($stmt->affected_rows > 0)
{
    returnWithInfo($inData["firstName"], $inData["lastName"], $nextUserId);
}
else
{
    returnWithError("Error Creating User");
}

// Close the statement and connection
$stmt->close();
$conn->close();

?>
