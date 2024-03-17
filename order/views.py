from django.shortcuts import HttpResponse, render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from cart.cart import Cart
from .models import Order, OrderItem
from .forms import OrderCreateForm
from .pdfcreator import renderPdf



from django.http import Http404
from django.shortcuts import HttpResponse, render, redirect, get_object_or_404

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import razorpay

# razorpay client config
razorpay_client = razorpay.Client(
    auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))


# --------------------------------- PAYMENT PAGE ---------------------------------
def payment(request):
    amount = 20000
    currency = request.session.get('currency', 'INR')
    # Create a Razorpay Order
    razorpay_order = razorpay_client.order.create(
        dict(
            amount=amount,
            currency='INR',
            payment_capture='0'
        )
    )

    # order id of newly created order.
    razorpay_order_id = razorpay_order['id']
    callback_url = 'payment-handler/'
    context = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_merchant_key': settings.RAZOR_KEY_ID,
        'razorpay_amount': amount,
        'currency': currency,
        'callback_url': callback_url,
        'total_amount': amount / 100,
    }
    return render(request, 'order/payment.html', context)




@csrf_exempt
@login_required
def paymenthandler(request):
    # only accept POST request.
    if request.method == "POST":
        amount = 20000
        try:
            # get the required parameters from post request.
            payment_id = request.POST.get('razorpay_payment_id', '')
            razorpay_order_id = request.POST.get('razorpay_order_id', '')
            signature = request.POST.get('razorpay_signature', '')

            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }

            # verify the payment signature.

            signature = razorpay_client.utility.verify_payment_signature(
                params_dict)
            if signature is not None:

                try:
                    # capture the payemt
                    razorpay_client.payment.capture(payment_id, amount)

                    # render success page on successful caputre of payment
                    return render(request, 'order/payment-successful.html')
                except Exception as e:
                    print(e)
                    # if there is an error while capturing payment.
                    return render(request, 'payment-aborted.html')
            else:
                print('signature verification fails')
                # if signature verification fails.
                return render(request, 'payment-fail.html')
        except Exception as e:
            print(e)
            return render(request, 'payment-aborted.html')
    else:
        # if other than POST request is made.
        return render(request, 'payment-aborted.html')

def order_create(request):
	cart = Cart(request)
	if request.user.is_authenticated:
		customer = get_object_or_404(User, id=request.user.id)
		form = OrderCreateForm(request.POST or None, initial={"name": customer.first_name, "email": customer.email})
		if request.method == 'POST':
			if form.is_valid():
				order = form.save(commit=False)
				order.customer = User.objects.get(id=request.user.id)
				order.payable = cart.get_total_price()
				order.totalbook = len(cart) # len(cart.cart) // number of individual book
				order.save()

				for item in cart:
					OrderItem.objects.create(
						order=order, 
						book=item['book'], 
						price=item['price'], 
						quantity=item['quantity']
						)
				cart.clear()
				return render(request, 'order/successfull.html', {'order': order})

			else:
				messages.error(request, "Fill out your information correctly.")

		if len(cart) > 0:
			return render(request, 'order/payment.html', {"form": form})
		else:
			return redirect('store:books')
	else:
		return redirect('store:signin')
			
def order_list(request):
	my_order = Order.objects.filter(customer_id = request.user.id).order_by('-created')
	paginator = Paginator(my_order, 5)
	page = request.GET.get('page')
	myorder = paginator.get_page(page)

	return render(request, 'order/list.html', {"myorder": myorder})

def order_details(request, id):
	order_summary = get_object_or_404(Order, id=id)

	if order_summary.customer_id != request.user.id:
		return redirect('store:index')

	orderedItem = OrderItem.objects.filter(order_id=id)
	context = {
		"o_summary": order_summary,
		"o_item": orderedItem
	}
	return render(request, 'order/details.html', context)

