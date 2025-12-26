import { useState } from 'react'
import './LoginReg.css'
import back_icon from '../Assets/back.png'

function LoginReg() 
{
  const app_name = 'cop4331-project.online'
  function buildPath(route:string) : string
  {
      if (process.env.NODE_ENV != 'development') 
      {
          return 'http://' + app_name +  ':5000/' + route;
      }
      else
      {        
          return 'http://localhost:5000/' + route;
      }
  }

  const [state, setState] = useState("Welcome");
  const [message, setMessage] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUserame] = useState("");
  const [password, setPassword] = useState("");

  async function doRegister(event: any) : Promise<void>
  {
    event.preventDefault();
    var obj = {username:username,password:password,displayName:displayName,email:email};
    var js = JSON.stringify(obj);

    try
    {    
        const response = await fetch(buildPath('api/register'),
            {method:'POST',body:js,headers:{'Content-Type': 'application/json'}});

        var res = JSON.parse(await response.text());

        if( res.id <= 0 )
        {
            // setMessage('User/Password combination incorrect');
        }
        else
        {

            sendEmail(email, res.id)
            setState("Welcome");
        }
    }
    catch(error:any)
    {
        alert(error.toString());
        return;
    } 

  };

  async function sendEmail(email:string, id:string): Promise<void>
  {
      let obj = {userId:id,email:email};
      let js = JSON.stringify(obj);
      try
      {
        const response = await fetch(buildPath('api/sendVerificationEmail'), {
          method: 'POST',
          body: js,
          headers: { 'Content-Type': 'application/json' },
        });

          // Parse the response safely
          const resText = await response.text();
          if (!resText) {
            console.error("Empty response received from the server");
            return;
          }

          console.log("Email Sent");
        
      }
      catch
      {

      }

  }

  async function doLogin(event: any) : Promise<void>
  {
    event.preventDefault();
    var obj = {username:username,password:password};
    var js = JSON.stringify(obj);

    try
    {    
        const response = await fetch(buildPath('api/login'),
            {method:'POST',body:js,headers:{'Content-Type': 'application/json'}});

        var res = JSON.parse(await response.text());

        if( res.id <= 0 )
        {
            setMessage('User/Password incorrect');
        }
        else
        {
            var user = {username:res.Username, id:res.id, displayName:res.DisplayName, email:res.Email, verified:res.Verified}
            localStorage.setItem('user_data', JSON.stringify(user));
            // Clear the input fields after successful login
            setUserame("");
            setPassword("");
            setMessage('Login successful');
            window.location.href = '/menu';
        }
    }
    catch(error:any)
    {
        alert(error.toString());
        return;
    }

    
  };

  function forgotPasswordRoute() : void
  {
    window.location.href = '/email-recovery'
  }

  function handleSetRegDisplayName( e: any ) : void
  {
    setDisplayName( e.target.value );
  }

  function handleSetRegEmail( e: any ) : void
  {
    setEmail( e.target.value );
  }

  function handleSetRegUsername( e: any ) : void
  {
    setUserame( e.target.value );
  }

  function handleSetRegPassword( e: any ) : void
  {
    setPassword( e.target.value );
  }

  return (
    <div className='container'>
        <div className="header">{state}</div>
        {state === "Welcome"?<div></div>:<div className="backArrow"><img src={back_icon} alt='' onClick={() => setState("Welcome")}/></div>}
      <div className="inputs">
      {state === "Welcome"?<div></div>:<div className="input"><input type="text" id='displayName' onChange={handleSetRegDisplayName} placeholder='Name' autoComplete='off'/></div>}
      {state === "Welcome"?<div></div>:<div className="input"><input type="text" id='email' onChange={handleSetRegEmail} placeholder='Email' autoComplete='off'/></div>}

        <div className="input">
          <input type="text" id='username' value={username} onChange={handleSetRegUsername} placeholder='Username' autoComplete='new-Username'/>
        </div>
        <div className="input">
          <input type="password" id='password' value={password} onChange={handleSetRegPassword}  placeholder='Password' autoComplete='new-Password'/>
        </div>
      </div>
      {state === "Register"?<div></div>:<div className="forgotxLorR">
        <div className="forgotPassword" onClick={forgotPasswordRoute}>Forgot Your Password?</div>
        <div className="LorR" onClick={() => setState("Register")}>New User?</div>
      </div>}

        {state === "Welcome"?<div className="submit" onClick={doLogin}>Login</div>:<div className="submit" onClick={doRegister}>Register</div>}
        <div id="resultText">{message}</div>
    </div>
  )
};

export default LoginReg
