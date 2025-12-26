const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const { MongoClient } = require('mongodb');
const { ObjectId } = require('mongodb');
const nodemailer = require('nodemailer');
const jwt = require('jsonwebtoken');
require('dotenv').config(); // Load environment variables from .env file
const JWT_SECRET = process.env.JWT_SECRET || "K5J9#s!z4o!7oRbt@xNxO3FdH2w6p+fKzA3b1g2LZt8FzQ1zTzK5mJ9oR8bK7Yw"; 
const uri = process.env.MONGO_URI || "mongodb+srv://server:LargeProjectServer@cluster0.3ygv0.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0";



const transporter = nodemailer.createTransport({
    // service: 'Gmail',
    host: 'smtp.gmail.com',
    port: 587,
    auth: {
        user: 'cop4331group3@gmail.com',
        pass: 'dxjv nrzx zyub cjbh'
    },
});


const app = express();
app.use(cors());
app.use(bodyParser.json());

const client = new MongoClient(uri);

app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader(
        'Access-Control-Allow-Headers',
        'Origin, X-Requested-With, Content-Type, Accept, Authorization'
    );
    res.setHeader(
        'Access-Control-Allow-Methods',
        'GET, POST, PATCH, DELETE, OPTIONS'
    );
    next();
});

app.listen(5000); // start Node + Express server on port 5000


app.post('/api/register', async (req, res, next) =>
{
// incoming: username, password, firstName, lastName, phoneNum, email
// outgoing: id, firstName, lastName, error
    const { username, password, displayName, email } = req.body;
    let id = '';
    let un = '';
    let error = '';
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

    try
    {
        if (!emailPattern.test(email))
        {
            error = 'Invalid email format';
            return res.status(400).json({ id, Username: un, error });
        }

        await client.connect();
        const db = client.db('POOSD-Large-Project');

        // Check if the user already exists (by email or username)
        const existingUser = await db.collection('User').findOne({$or: [{ Username: username }, { Email: email }]});
        if (existingUser)
        {
            error = 'Username or email already exists';
            return res.status(400).json({ id,  Username: un, error });
        }

        // Create a new user
        const newUser =
        {
            Username : username,
            Password: password,
            Email: email,
            Verified: false,
            DisplayName: displayName,
        };

        // Save user to database
        await db.collection('User').insertOne(newUser);

        const user = await db.collection('User').find({ Username: username }).toArray();

        if (user.length > 0) {
            id = user[0]._id.toString();
            un = user[0].Username;
        }

        const ret = {id: id, Username: un, error: ''};
        res.status(200).json(ret);
    } catch (err)
    {
        console.error(err);
        error = 'An error has occurred\nUnable to register user';
        res.status(500).json({ id, Username: un, error });
    }
});

app.post('/api/login', async (req, res, next) =>
{
// incoming: login, password
// outgoing: id, firstName, lastName, error
    let id = '';
    let un = '';
    let dn = '';
    let em = '';
    let ver = '';
    let error = '';
    const {username, password} = req.body;
    try {
        await client.connect();
        const db = client.db('POOSD-Large-Project');

        const user = await db.collection('User').find({Username: username, Password: password,}).toArray();
        if (user.length > 0) {
            id = user[0]._id.toString();
            un = user[0].Username;
            dn = user[0].DisplayName;
            em = user[0].Email;
            ver = user[0].Verified;
            res.status(200).json({ id : id, Username: un, DisplayName : dn, Email : em, Verified : ver, error: '' });
        } else {
            error = 'Invalid username or password';
            res.status(400).json({ id: id, Username: un, DisplayName : dn, Email : em, error });
        }
    } catch (err)
    {
        console.error(err);
        error = 'An error has occurred\nUnable to login';
        res.status(500).json({ id : id, Username: un, DisplayName : dn, Email : em, error });
    }
});

app.post('/api/getPublicSets', async (req, res, next) => 
{
  // incoming: nameSearch, topicSearch
  // outgoing: results[], error
  var error = '';

  const { nameSearch = '', topicSearch = '' } = req.body; // Default to empty strings if not provided
  
  try 
  { 
     await client.connect();

    const db = client.db("POOSD-Large-Project");

    const results = await db.collection('CardSet').find(
    {
        Published: true,
        Name: { $regex: new RegExp(nameSearch + '.*', 'i') },
        Topic: { $regex: new RegExp(topicSearch + '.*', 'i') }
    },
      {
        projection: { Name: 1, Topic: 1, _id: 1 } // Return only necessary fields
      }
    ).toArray();  

    const _ret = results.map(result => (
    {
      Name: result.Name,
      Topic: result.Topic,
      _id: result._id
    }));
  
    const ret = { results: _ret, error: error };
    res.status(200).json(ret);
    
  } catch (err) 
  {
    console.error("Error retrieving data:", err);
    res.status(500).json({ results: [], error: "Server Error" })
  }

});

app.post('/api/createCardSet', async (req, res) =>
{
  // incoming: Name, Topic, UserId, Published
  // outgoing: success, error
  
  // Extract fields from the request body
  const { Name, Topic, UserId, Published} = req.body;
  var SetID = 1;

  // Validate required fields
  if (!Name || !Topic || !UserId) 
  {
      return res.status(400).json({ success: false, error: "Missing required fields" });
  }
  var userId
  var ObjectId = require('mongodb').ObjectId;
  userId = new ObjectId(UserId)

  try
  {
      await client.connect();
      const db = client.db("POOSD-Large-Project"); // Replace with your database name
        
      // Create the new card set object
      const newCardSet = 
      {
          Name,
          SetID, 
          UserID : userId,
          Topic,
          Published
      };

      // Insert the new card set into the CardSet collection
      const result = await db.collection('CardSet').insertOne(newCardSet);

      res.status(201).json({ success: true, id: result.insertedId,});
  } catch (error) {
      console.error("Error creating card set:", error);
      res.status(500).json({ success: false, error: "Failed to create card set" });
  } 
});

app.post('/api/updateCardSet', async (req, res) =>
{
  // Incoming id, Name, Topic
  // Outgoing success, error

  const { id, Name, Topic } = req.body; // Expecting id of the card set and optional fields to update

  // Validate required fields
  if (!id)
  {
      return res.status(400).json({ success: false, error: "CardSet ID is required" });
  }

  // Prepare the update object
  const updateFields = {};
  if (Name && Name.trim() !== '') {
      updateFields.Name = Name.trim(); // Trim and add to update object if not empty
  }
  if (Topic && Topic.trim() !== '') {
      updateFields.Topic = Topic.trim(); // Trim and add to update object if not empty
  }

  // If there are no fields to update, return an error
  if (Object.keys(updateFields).length === 0)
  {
      return res.status(400).json({ success: false, error: "No fields to update" });
  }

  try {
      await client.connect();
      const db = client.db("POOSD-Large-Project");
      
      var ObjectId = require('mongodb').ObjectId;


      // Update the card set
      const result = await db.collection('CardSet').updateOne(
          { _id: new ObjectId(id) }, // Find by ID
          { $set: updateFields } // Update fields
      );

      if (result.modifiedCount === 0) {
          return res.status(404).json({ success: false, error: "CardSet not found or no changes made" });
      }

      res.status(200).json({ success: true, message: "CardSet updated successfully" });
  } catch (error) {
      console.error("Error updating card set:", error);
      res.status(500).json({ success: false, error: "Failed to update card set" });
  }
});

app.post('/api/deleteCardSet', async (req, res) => 
{
  const { id } = req.body; // Expecting id of the CardSet to delete


  // Validate required fields
  if (!id)
  {
      return res.status(400).json({ success: false, error: "CardSet ID is required" });
  }

  var ObjectId = require('mongodb').ObjectId;
  _id = new ObjectId(id);
  try 
  {
     await client.connect();
    const db = client.db("POOSD-Large-Project"); // Replace with your database name
    
    // First, find the CardSet to get the SetID
    const cardSet = await db.collection('CardSet').findOne({ _id});

    if (!cardSet)
    {
        return res.status(404).json({ success: false, error: "CardSet not found" });
    }


    // Delete all cards associated with this CardSet using SetID
    const deleteCardsResult = await db.collection('Cards').deleteMany({ SetID: _id });

    // Delete the CardSet itself
    const deleteCardSetResult = await db.collection('CardSet').deleteOne({ _id });

    if (deleteCardSetResult.deletedCount === 0) 
    {
        return res.status(404).json({ success: false, error: "Failed to delete CardSet" });
    }

    // Return a response with the number of cards deleted and confirmation of CardSet deletion
    res.status(200).json(
    {
        success: true,
        message: "CardSet deleted successfully",
        cardsDeleted: deleteCardsResult.deletedCount
    });
    } catch (error)
    {
      console.error("Error deleting card set:", error);
      res.status(500).json({ success: false, error: "Failed to delete card set" });
    }
});

app.delete('/api/deleteUser', async (req, res) => {
    const { userId } = req.body;

    try {
        const userObjectId = new ObjectId(userId);

        // Start a MongoDB session
        const session = await client.startSession();

        // Begin transaction
        await session.withTransaction(async () => {
            // Delete all card sets owned by the user
            await db.collection('CardSet').deleteMany({ UserId: userObjectId }, { session });

            // Delete the user from the User collection
            await db.collection('User').deleteOne({ _id: userObjectId }, { session });
        });

        // Return success response
        res.status(200).json({ success: true });

    } catch (error) {
        res.status(500).json({ success: false, message: "Failed to delete user" });
    }
});

app.post('/api/getUserSets', async (req, res) => {
    const { userId } = req.body;
  
    if (!userId) {
      console.error("User ID is missing in request body.");
      return res.status(400).json({ success: false, message: 'User ID is required', sets: [] });
    }
  
    try {
      // Check if MongoDB client is connected
      if (!client.topology || !client.topology.isConnected()) {
        console.error("MongoDB client is not connected.");
        return res.status(500).json({ success: false, message: 'Database not connected' });
      }
  
      const db = client.db("POOSD-Large-Project");
      const userObjectId = new ObjectId(userId);
  
      // Query for documents with the given UserID ObjectId
      const userSets = await db.collection('CardSet').find({ UserID: userObjectId }).toArray();
  
      if (!userSets || userSets.length === 0) {
        console.error("No sets found for the given UserID.");
        return res.status(200).json({ success: false, sets: [] });
      }
  
      res.status(200).json({ success: true, sets: userSets });
    } catch (error) {
      console.error("Error retrieving user sets:", error);
      res.status(500).json({ success: false, message: 'Failed to fetch user sets', sets: [] });
    }
  });

app.post('/api/getCard', async (req, res, next) => 
{
    // incoming: id (setID)
    // outgoing: results[], error
    var error = '';

    const {id} = req.body; // Default to empty strings if not provided
    
    if (!id) 
    {
        return res.status(400).json({ success: false, error: "CardSet ID is required" });
    }   

    try 
    { 
        await client.connect();
        const db = client.db("POOSD-Large-Project");
        var setObjectID
        var ObjectId = require('mongodb').ObjectId;
        try {
             setObjectID = new ObjectId(id);
        }
        catch (error) {
            return res.status(400).json({ success: false, error: "Invalid CardSet ID format" });
        }
       
        const cards = await db.collection('Cards').find({SetID : setObjectID}).sort({_id: 1}).toArray();
    
    const _ret = cards.map(card => (
    {
        Term: card.Term,
        Definition: card.Definition,
        _id: card._id.toString()
    }));
    const ret = { results: _ret, error: error };
    res.status(200).json(ret);
    
    } catch (err) 
    {
        console.error("Error retrieving data:", err);
        res.status(500).json({ results: [], error: "Server Error" })
    }

});                         

app.post('/api/createCard', async (req, res) => 
{
    // incoming: Term, Definition, setID
    // outgoing: results[], error

    const { Term, Definition, setID } = req.body; // Expecting Term, Definition, and CardId as input

    // Validate the required fields
    if (!Term || !Definition || !setID) 
    {
        return res.status(400).json({ success: false, error: "Term, Definition, and setId are required" });
    }
;
    try
    {
        var setObjectID = new ObjectId(setID); // Convert CardId string to ObjectId
    } catch (error) 
    {
        return res.status(400).json({ success: false, error: "Invalid CardId format" });
    }

    try
    {
        await client.connect();
        const db = client.db("POOSD-Large-Project"); // Replace with your database name

        // Insert the new card into the Card collection
        const newCard = 
        {
            Term: Term,
            Definition: Definition,
            SetID: setObjectID // Reference to the CardSet ObjectId
        };

        const result = await db.collection('Cards').insertOne(newCard);

        // Return the newly created card details including the generated _id
        res.status(201).json(
        {
            success: true,
            card: {
                _id: result.insertedId.toString(),
                Term: newCard.Term,
                Definition: newCard.Definition
            }
        });
    } catch (error)
    {
        console.error("Error creating card:", error);
        res.status(500).json({ success: false, error: "Failed to create card" });
    }
});

//delete card
app.post('/api/deleteCard', async (req, res) => {
// Extract the card ID from the request body
const { id } = req.body;

// Validate the input to ensure the ID is provided
if (!id) {
    return res.status(400).json({ success: false, error: "Card ID is required" });
}

try {
    // Connect to the database
    await client.connect();
    const db = client.db("POOSD-Large-Project");

    // Convert the card ID to a MongoDB ObjectId
    const cardObjectId = new ObjectId(id);

    // Attempt to delete the card with the specified ID
    const result = await db.collection('Cards').deleteOne({ _id: cardObjectId });

    // Check if a card was actually deleted
    if (result.deletedCount === 0) {
        return res.status(404).json({ success: false, error: "Card not found" });
    }

    // Return a success response if the card was deleted
    res.status(200).json({ success: true, message: "Card deleted successfully" });
} catch (error) {
    console.error("Error deleting card:", error);

    // Return an error response if something goes wrong
    res.status(500).json({ success: false, error: "Failed to delete card" });
}
});

// update card
app.post('/api/updateCard', async (req, res) => {
    // Extract the required fields from the request body
    const { id, question, answer } = req.body;
    // console.log(req.body);

    // Validate input to ensure all fields are provided
    if (!id || !question || !answer) {
        return res.status(400).json({ success: false, error: "Card ID, question, and answer are required" });
    }

    try {
        // Connect to the database
        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Convert the card ID to a MongoDB ObjectId
        const cardObjectId = new ObjectId(id);

        // Update the card with the specified ID
        const result = await db.collection('Cards').updateOne(
            { _id: cardObjectId }, // Filter by card ID
            { $set: { Term: question, Definition: answer } } // Update fields
        );

        // Check if the card was found and updated
        if (result.matchedCount === 0) {
            return res.status(404).json({ success: false, error: "Card not found" });
        }

        // Return a success response if the card was updated
        res.status(200).json({ success: true, message: "Card updated successfully" });
    } catch (error) {
        console.error("Error updating card:", error);

        // Return an error response if something goes wrong
        res.status(500).json({ success: false, error: "Failed to update card" });
    }
});

/*********************************************Email verification and recovery*****************************************/

// Email verification endpoint
app.post('/api/sendVerificationEmail', async (req, res) => {
    const { userId, email } = req.body;
    if (!userId || !email) {
        return res.status(400).json({ success: false, error: "User ID and email are required" });
    }

    // const verificationToken = crypto.randomBytes(32).toString('hex');
    const verificationToken = jwt.sign({ userId }, JWT_SECRET, { expiresIn: '1h' });
    // const baseUrl = process.env.NODE_ENV === 'development'
    // ? 'https://cop4331-project.online' 
    // : 'http://localhost:5000'; 

    const baseUrl = "http://cop4331-project.online:5000";
    // const baseUrl = "http://localhost:5173"
    // const baseUrl = "http://localhost:5000";

    const verificationLink = `${baseUrl}/verify-email?token=${verificationToken}`;
    const verificationTokenExpiry = Date.now() + 3600000; // 1 hour


    try {
        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Store the verification token in the database
        const updateResult = await db.collection('User').updateOne(
            { _id: new ObjectId(userId) },
            { $set: { verificationToken, verificationTokenExpiry, Verified: false } }
        );

        // Send the verification email
        await transporter.sendMail({
            to: email,
            subject: 'Verify Your Email Address',
            text: `Please verify your email by clicking the following link: ${verificationLink}`,
        });

        res.status(200).json({ success: true, message: "Verification email sent" });
    } catch (error) {
        console.error("Error sending verification email:", error);
        res.status(500).json({ success: false, error: "Failed to send verification email" });
    }
});

app.get('/verify-email', async (req, res) => {
    const { token } = req.query;
    // console.log("This is a token: " + req.query.token);

    if (!token) {
        return res.status(400).json({ success: false, error: "Verification token is required" });
    }

    try {
        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Check if the user is already verified
        const user = await db.collection('User').findOne({
            verificationToken: token,
            verificationTokenExpiry: { $gt: Date.now() }, // Check token expiry
        });

        if (!user) {
            return res.status(400).json({ success: false, error: "Invalid or expired token" });
        }

        // Mark the user as verified
        const updateResult = await db.collection('User').updateOne(
            { _id: user._id },
            {
                $set: { Verified: true },
                $unset: { verificationToken: "", verificationTokenExpiry: "" },
            }
        );

        if (updateResult.modifiedCount === 0) {
            return res.status(500).json({ success: false, error: "Failed to update user verification status" });
        }

        // Respond with JSON to match the front-end expectations
        res.status(200).json({ success: true });
    } catch (error) {
        console.error("Error verifying email:", error);
        res.status(500).json({ success: false, error: "Failed to verify email" });
    }
});




// Password recovery request endpoint
app.post('/api/sendRecoveryEmail', async (req, res) => {
    const { email } = req.body;
    if (!email) {
        return res.status(400).json({ success: false, error: "Email is required" });
    }

    const recoveryToken = jwt.sign({ email }, JWT_SECRET, { expiresIn: '1h' });
    // : 'http://localhost:5173';

    const baseUrl = "http://cop4331-project.online"
    const recoveryLink = `${baseUrl}/recover-password?token=${recoveryToken}`;
    const recoveryTokenExpiry = Date.now() + 3600000;

    try {
        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Store the recovery token in the database
        const result = await db.collection('User').updateOne(
            { Email: email },
            { $set: { recoveryToken, recoveryTokenExpiry } }
        );

        if (result.matchedCount === 0) {
            return res.status(404).json({ success: false, error: "Email not found" });
        }

        // Send the recovery email
        await transporter.sendMail({
            to: email,
            subject: 'Password Recovery',
            text: `You can reset your password by clicking the following link: ${recoveryLink}`,
        });

        res.status(200).json({ success: true, message: "Password recovery email sent" });
    } catch (error) {
        console.error("Error sending recovery email:", error);
        res.status(500).json({ success: false, error: "Failed to send recovery email" });
    }
});


app.get('/api/recover-password', async (req, res) => {
    const { token } = req.query; // Token from query parameters

    if (!token) {
        return res.status(400).json({ success: false, error: "Recovery token is required" });
    }

    try {
        // Verify the token
        const decoded = jwt.verify(token, JWT_SECRET);
        const email = decoded.email;

        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Check if token exists and is not expired
        const user = await db.collection('User').findOne({
            Email: email,
            recoveryToken: token,
            recoveryTokenExpiry: { $gt: Date.now() },
        });

        if (!user) {
            return res.status(400).json({ success: false, error: "Invalid or expired recovery token" });
        }

        res.status(200).json({
            success: true,
            message: "Recovery token is valid",
            email, // Optionally include the user's email for client-side convenience
        });
    } catch (error) {
        console.error("Error validating recovery token:", error);

        // Distinguish between invalid and expired tokens
        if (error.name === 'TokenExpiredError') {
            return res.status(400).json({ success: false, error: "Recovery token has expired" });
        }

        res.status(400).json({ success: false, error: "Invalid recovery token" });
    }
});

// Reset password endpoint
app.post('/api/resetPassword', async (req, res) => {
    const { token, newPassword } = req.body;

    if (!token || !newPassword) {
        return res.status(400).json({ success: false, error: "Token and new password are required" });
    }

    try {
        const decoded = jwt.verify(token, JWT_SECRET);
        const email = decoded.email;


        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Check the user's recovery token and expiry in the database
        const user = await db.collection('User').findOne({
            Email: email,
            recoveryToken: token, 
            recoveryTokenExpiry: { $gt: Date.now() }, 
        });


        if (!user) {
            console.error("No matching user or expired token:", { email, token });
            return res.status(400).json({ success: false, error: "Invalid or expired token" });
        }

        const result = await db.collection('User').findOneAndUpdate(
            { Email: email, recoveryToken: token, recoveryTokenExpiry: { $gt: Date.now() } },
            { 
                $set: { Password: newPassword }, 
                $unset: { recoveryToken: "", recoveryTokenExpiry: "" } 
            },
            { returnDocument: 'after' } 
        );


        // Check if password update was successful
        if (result && result.value && result.value.Password !== newPassword) {
            console.error("Password did not update properly:", { email, token });
            return res.status(400).json({ success: false, error: "Failed to reset password" });
        }

        // If update is successful, return success
        res.status(200).json({ success: true, message: "Password reset successfully" });
    } catch (error) {
        console.error("Error resetting password:", error);

        if (error.name === 'TokenExpiredError') {
            return res.status(400).json({ success: false, error: "Recovery token has expired" });
        }

        res.status(500).json({ success: false, error: "Failed to reset password" });
    }
});






app.post('/api/checkVerificationStatus', async (req, res) => {
    const { userId } = req.body;

    if (!userId) {
        return res.status(400).json({ success: false, error: "User ID is required" });
    }

    try {
        await client.connect();
        const db = client.db("POOSD-Large-Project");

        // Find the user by their userId
        const user = await db.collection('User').findOne({ _id: new ObjectId(userId) });

        if (!user) {
            return res.status(404).json({ success: false, error: "User not found" });
        }

        // Return the verification status
        res.status(200).json({ success: true, verified: user.Verified });
    } catch (error) {
        console.error("Error checking verification status:", error);
        res.status(500).json({ success: false, error: "Failed to check verification status" });
    }
});
