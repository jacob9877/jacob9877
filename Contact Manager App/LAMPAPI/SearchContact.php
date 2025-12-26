<?php

$inData = getRequestInfo();

// Default response values
$searchResults = [];
$searchCount = 0;

$conn = new mysqli("localhost", "TheBeast", "WeLoveCOP4331", "COP4331");

if ($conn->connect_error) 
{
    returnWithError($conn->connect_error);
} 
else
{
    // Prepare the SQL statement for searching contacts
    $stmt = $conn->prepare("SELECT * FROM Contacts WHERE (Name LIKE ? OR Phone LIKE ? OR Email LIKE ?) AND UserID = ?");
    if (!$stmt) {
        returnWithError("Prepare failed: " . $conn->error);
    }

    $likeSearch = "%" . $inData["query"] . "%";
    $stmt->bind_param("ssss", $likeSearch, $likeSearch, $likeSearch, $inData["userId"]);

    if (!$stmt->execute()) {
        returnWithError("Execute failed: " . $stmt->error);
    }
    
    $result = $stmt->get_result();
    
    // Build the response data
    while ($row = $result->fetch_assoc())
    {
        $searchResults[] = $row;
    }
    
    if (empty($searchResults))
    {
        returnWithError("No Records Found");
    }
    else
    {
        returnWithInfo($searchResults);
    }
    
    $stmt->close();
    $conn->close();
}

function getRequestInfo()
{
    $json = file_get_contents('php://input');
    if (empty($json)) {
        return ['error' => 'No input data'];
    }
    
    $data = json_decode($json, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        return ['error' => 'Invalid JSON: ' . json_last_error_msg()];
    }
    
    return $data;
}

function sendResultInfoAsJson($obj)
{
    header('Content-type: application/json');
    echo json_encode($obj);
}

function returnWithError($err)
{
    $retValue = ['error' => $err];
    sendResultInfoAsJson($retValue);
    error_log("Error: " . $err); // Log error to server logs
}

function returnWithInfo($searchResults)
{
    $retValue = ['results' => $searchResults, 'error' => 'None'];
    sendResultInfoAsJson($retValue);
    error_log("Results: " . print_r($searchResults, true)); // Log results to server logs
}

?>
