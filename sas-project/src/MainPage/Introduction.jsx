import { Link } from 'react-router-dom';

function Introductions(){

    return(<>
    <div className="Introduction-container">
    <h1> Your Perfect Night Out</h1><i></i>
    <p>This is a planner for what you can do after a long day of work or just the end of week which includes pubs, clubs, restaurants.<br/>You name it! Anything that you can think of that takes your mind off work.</p>
    <Link to="/vibe" className="links">Plan Your Night Out</Link>
    </div>
    
    </>)

}
export default Introductions