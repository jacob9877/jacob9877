import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

const EmailCheck = () => {
    const [message, setMessage] = useState('');
    // const [loading, setLoading] = useState(true);
    const [searchParams] = useSearchParams();
    // const location = useLocation();

    useEffect(() => {
        const token = searchParams.get('token');
        console.log("This is the token: ", token);

        if (!token) {
            setMessage('Verification token is required');
            // setLoading(false);
            return;
        }

        // Send a request to the backend to verify the token

            const verifyEmail = async () => {
                try {
                    const response = await fetch('/verify-email?token=' + token);
                    console.log(response);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
        
                    const data = await response.json();
                    console.log("This is Data: ", data);
                    if (data.success) {
                        setMessage('Email successfully verified!');
                    } else {
                        setMessage(data.error || 'Something went wrong. Please try again.');
                    }
                } catch (error) {
                    setMessage('An error occurred while verifying your email.');
                }
            };
        
            // const searchParams = new URLSearchParams(location.search);
            // const token = searchParams.get('token');
        
            verifyEmail();
        }, []);
        

    return (
        <div>
            <h2>Email Verification</h2>
                <p>{message}</p>
        </div>
    );
};

export default EmailCheck;
