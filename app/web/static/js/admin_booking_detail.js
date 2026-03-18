window.approvePayment = async function(id){

    try{

        const res = await fetch(`/admin/bookings/${id}/approve`, {
            method: "POST",
            credentials: "same-origin"
        })

        if(!res.ok){
            throw new Error("Approval failed")
        }

        window.location.href =
            "/admin/bookings?success=Payment approved"

    }catch(err){

        alert("Payment approval failed")

    }

}


window.rejectPayment = async function(id){

    const note = prompt("Reason for rejection")

    if(!note) return

    try{

        const res = await fetch(
            `/admin/bookings/${id}/reject?note=${encodeURIComponent(note)}`,
            {
                method: "POST",
                credentials: "same-origin"
            }
        )

        if(!res.ok){
            throw new Error("Reject failed")
        }

        window.location.href =
            "/admin/bookings?error=Payment rejected"

    }catch(err){

        alert("Payment rejection failed")

    }

}








async function approveCredit(bookingId){

    if(!confirm("Approve this booking for credit processing?")) return;

    try{

        let res = await fetch(`/admin/bookings/${bookingId}/approve-credit`, {
            method: "POST"
        });

        if(!res.ok){
            alert("Failed to approve credit");
            return;
        }

        alert("Credit approved successfully");

        window.location.reload();

    }catch(err){
        console.error(err);
        alert("Error approving credit");
    }

}