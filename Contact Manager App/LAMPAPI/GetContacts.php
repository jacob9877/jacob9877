<?php
function getRequestInfo()
{
    return json_decode(file_get_contents('php://input'), true);
}

function sendResultInfoAsJson($obj)
{
    header('Content-type: application/json');
    echo $obj;
}

function returnWithError($err)
{
    $retValue = '{"results":[],"error":"' . $err . '"}';
    sendResultInfoAsJson($retValue);
}

function returnWithInfo($searchResults)
{
    $retValue = '{"results":[' . $searchResults . '],"error":""}';
    sendResultInfoAsJson($retValue);
}

$inData = getRequestInfo();

$conn = new mysqli("localhost", "TheBeast", "WeLoveCOP4331", "COP4331");
if ($conn->connect_error)
{
    returnWithError($conn->connect_error);
}
else
{
    $stmt = $conn->prepare("SELECT ID, Name, Phone, Email, DateCreated FROM Contacts WHERE UserID=?");
    $stmt->bind_param("i", $inData["userId"]);
    $stmt->execute();
    $result = $stmt->get_result();
    $searchResults = "";
    while($row = $result->fetch_assoc())
    {
        if ($searchResults != "")
        {
            $searchResults .= ",";
        }
        $searchResults .= json_encode([
            "ID" => $row["ID"],
            "Name" => $row["Name"],
            "Phone" => $row["Phone"],
            "Email" => $row["Email"],
	    "DateCreated" => $row["DateCreated"]
        ]);
    }
    if ($searchResults == "")
    {
        returnWithError("No Contacts Found");
    }
    else
    {
        returnWithInfo($searchResults);
    }
    $stmt->close();
    $conn->close();
}
?>