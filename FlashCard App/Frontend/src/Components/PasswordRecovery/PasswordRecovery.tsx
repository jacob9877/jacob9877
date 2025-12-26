import './PasswordRecovery.css'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom';
import arrow_icon from "../Assets/arrow.png"

function PasswordRecovery()
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

    const [newPassword, setNewPassword] = useState('');
    const [message, setMessageP] = useState('');
    const [searchParams] = useSearchParams();

    function backToLogin() {
        window.location.href = "/";
      }

    const token = searchParams.get('token');

    async function resetPassword(e:any) : Promise<void>
    {
        e.preventDefault();
        console.log("New password:", newPassword);
        console.log("This is the token: ",token);
        var obj = {token:token, newPassword:newPassword}
        var js = JSON.stringify(obj);

        try
        {
            const response = await fetch(buildPath('api/resetPassword'),
            {method:'POST',body:js,headers:{'Content-Type': 'application/json'}});

        var res = JSON.parse(await response.text());
        setMessageP(res.message);
        if(res.error)
        {
            setMessageP(res.error);
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

    function handleSetNewPassword(e:any) : void
    {
        setNewPassword(e.target.value)
    }



    return(
        <div>
            <div className="blurredBackground"></div>
            <div><img src={arrow_icon} id="backMenu" onClick={backToLogin} /></div>
            <div className='container'>
                <div className="inputs">
                <div className="headerEmail">Enter New Password</div>
                <div className="input"><input type="text" id='password' placeholder="New Password" onChange={handleSetNewPassword}/></div>
                </div>
                <div className="submit" onClick={resetPassword}>Submit</div>
                <div id="resultText">{message}</div>
            </div>
        </div>
    )
    
}

export default PasswordRecovery