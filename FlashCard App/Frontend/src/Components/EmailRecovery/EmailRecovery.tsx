import './EmailRecovery.css'
import { useState } from 'react'
import arrow_icon from "../Assets/arrow.png"

function EmailRecovery()
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

    const [email, setEmailR] = useState('');
    const [message, setMessageR] = useState('');

    function backToLogin() {
        window.location.href = "/";
      }

    async function sendReset(e: any) : Promise<void>
    {
        e.preventDefault();
        console.log("Email:", email);
        var obj = {email: email};
        var js = JSON.stringify(obj);

        try
        {
            const response = await fetch(buildPath("api/sendRecoveryEmail"),
            {method:'POST',body:js,headers:{'Content-Type': 'application/json'}});
            var res = JSON.parse(await response.text());
            setMessageR(res.message);
            if(res.error)
            {
                setMessageR(res.error);
            }
            if(res.success)
            {
                window.location.href = "/";
            }
            
            
        }
        catch
        {
            return;
        }
    }

    function handleSetEmail(e: any) : void
    {
        setEmailR(e.target.value);
    }



    return(
        <div>
            <div className="blurredBackground"></div>
            <div><img src={arrow_icon} id="backMenu" onClick={backToLogin} /></div>
            <div className='container'>
                <div className="inputs">
                <div className="headerEmail">Enter Your Email</div>
                <div className="input"><input type="text" id='email' placeholder="Your Email" onChange={handleSetEmail}/></div>
                </div>
                <div className="submit" onClick={sendReset}>Submit</div>
                <div id="resultText">{message}</div>
            </div>
        </div>
    )
}

export default EmailRecovery