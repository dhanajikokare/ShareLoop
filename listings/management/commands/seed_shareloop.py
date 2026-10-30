from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from listings.models import Category, Listing
from accounts.models import Address

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds database with Pune categories, demo users, and listings'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding ShareLoop database...'))

        # 1. Categories
        categories_data = [
            ('Electronics', 'bi-laptop', 'Laptops, tablets, monitors, and audio gear for study and work', 1),
            ('Cameras & Photography', 'bi-camera', 'DSLRs, mirrorless cameras, lenses, gimbals, and lighting', 2),
            ('Tools & Equipment', 'bi-tools', 'Drills, power tools, ladders, and home improvement equipment', 3),
            ('Home Appliances', 'bi-house-gear', 'Air purifiers, vacuum cleaners, steamers, and kitchen appliances', 4),
            ('Furniture & Decor', 'bi-lamp', 'Study chairs, desks, bean bags, and foldable furniture', 5),
            ('Books & Study Materials', 'bi-book', 'Engineering textbooks, competitive exam books, and novels', 6),
            ('Sports & Fitness', 'bi-bicycle', 'Cycles, badminton racquets, dumbbells, and cricket kits', 7),
            ('Travel & Camping', 'bi-compass', 'Tents, sleeping bags, trekking poles, and travel backpacks', 8),
            ('Party & Event Supplies', 'bi-balloon', 'Projectors, karaoke speakers, party lights, and decor', 9),
            ('Musical Instruments', 'bi-music-note-beamed', 'Acoustic guitars, keyboards, violins, and ukuleles', 10),
            ('Fashion & Traditional Wear', 'bi-handbag', 'Costumes, festive wear, blazers, and luggage', 11),
            ('Vehicles & Mobility', 'bi-ev-front', 'E-scooters, commuter cycles, and mobility accessories', 12),
        ]

        category_objs = {}
        for name, icon, desc, order in categories_data:
            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'icon_class': icon, 'description': desc, 'display_order': order, 'is_active': True}
            )
            category_objs[name] = cat
            if created:
                self.stdout.write(f"Created category: {name}")

        # 2. Users
        # Admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@shareloop.in',
                'first_name': 'ShareLoop',
                'last_name': 'Admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'user_type': 'BUSINESS',
            }
        )
        if created:
            admin_user.set_password('Admin@123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created admin user (admin / Admin@123)"))

        # Business Seller: Pune Gear & Tech
        biz_user, created = User.objects.get_or_create(
            username='pune_gear_hub',
            defaults={
                'email': 'contact@punegearhub.com',
                'first_name': 'Vikram',
                'last_name': 'Kulkarni',
                'user_type': 'BUSINESS',
                'phone_number': '+919822012345',
                'is_verified': True,
                'bio': 'Trusted rental & pre-owned camera and studio equipment hub in Baner, Pune.',
            }
        )
        if created:
            biz_user.set_password('Seller@123')
            biz_user.save()
            biz_user.profile.shop_name = 'Pune Gear & Studio Hub'
            biz_user.profile.shop_description = 'Professional video, audio, and creator gear rental & sales.'
            biz_user.profile.gst_number = '27AAAAA0000A1Z5'
            biz_user.profile.save()
            Address.objects.create(
                user=biz_user,
                full_name='Vikram Kulkarni',
                phone_number='+919822012345',
                address_line1='Shop 14, High Street Plaza',
                locality='Baner',
                city='Pune',
                state='Maharashtra',
                pincode='411045',
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS("Created business seller: pune_gear_hub"))

        # Individual User 1: Rahul (Kothrud)
        rahul, created = User.objects.get_or_create(
            username='rahul_deshmukh',
            defaults={
                'email': 'rahul.deshmukh@gmail.com',
                'first_name': 'Rahul',
                'last_name': 'Deshmukh',
                'user_type': 'INDIVIDUAL',
                'phone_number': '+919876543210',
                'is_verified': True,
                'bio': 'Software engineer in Kothrud. Happy to share books, tools, and tech items with neighbors.',
            }
        )
        if created:
            rahul.set_password('User@123')
            rahul.save()
            Address.objects.create(
                user=rahul,
                full_name='Rahul Deshmukh',
                phone_number='+919876543210',
                address_line1='B-402, Mayur Colony',
                locality='Kothrud',
                city='Pune',
                state='Maharashtra',
                pincode='411038',
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS("Created individual user: rahul_deshmukh"))

        # Individual User 2: Priya (Viman Nagar)
        priya, created = User.objects.get_or_create(
            username='priya_sharma',
            defaults={
                'email': 'priya.sharma@gmail.com',
                'first_name': 'Priya',
                'last_name': 'Sharma',
                'user_type': 'INDIVIDUAL',
                'phone_number': '+919855512345',
                'is_verified': True,
                'bio': 'Outdoor enthusiast & avid reader in Viman Nagar.',
            }
        )
        if created:
            priya.set_password('User@123')
            priya.save()
            Address.objects.create(
                user=priya,
                full_name='Priya Sharma',
                phone_number='+919855512345',
                address_line1='Flat 304, Sky Lounge',
                locality='Viman Nagar',
                city='Pune',
                state='Maharashtra',
                pincode='411014',
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS("Created individual user: priya_sharma"))

        # 3. Seed Sample Listings
        listings_data = [
            {
                'owner': biz_user,
                'category': category_objs['Cameras & Photography'],
                'title': 'Sony Alpha A7 IV Full-Frame Camera Kit (28-70mm Lens)',
                'description': 'Flagship 33MP full-frame hybrid camera with 4K 60p recording. Perfect for weddings, corporate video shoots, and weekend photography trips around Pune. Includes 2 batteries, 128GB high-speed SD card, and camera bag.',
                'item_condition': 'LIKE_NEW',
                'locality': 'Baner',
                'pincode': '411045',
                'can_rent': True,
                'can_borrow': False,
                'can_sell': False,
                'rent_price_per_day': Decimal('1500.00'),
                'rent_security_deposit': Decimal('5000.00'),
                'min_rental_days': 1,
                'max_rental_days': 14,
            },
            {
                'owner': rahul,
                'category': category_objs['Tools & Equipment'],
                'title': 'Bosch 550W Impact Drill Machine Kit with 100 Accessories',
                'description': 'Heavy-duty impact drill for home wall mounting, curtains, and DIY wood/metal work. Clean and working in prime condition. Available for neighbors to borrow completely free or rent.',
                'item_condition': 'GOOD',
                'locality': 'Kothrud',
                'pincode': '411038',
                'can_rent': True,
                'can_borrow': True,
                'can_sell': False,
                'rent_price_per_day': Decimal('200.00'),
                'rent_security_deposit': Decimal('500.00'),
                'is_free_borrow': True,
                'borrow_security_deposit': Decimal('300.00'),
                'borrow_max_days': 3,
                'min_rental_days': 1,
                'max_rental_days': 7,
            },
            {
                'owner': priya,
                'category': category_objs['Travel & Camping'],
                'title': 'Quechua 3-Person Waterproof Camping Tent + Groundsheet',
                'description': 'Dome tent easy to pitch in 10 minutes. Clean, waterproof, tested at Pawna Lake & Rajmachi treks. Available to borrow for free for responsible campers in Pune!',
                'item_condition': 'LIKE_NEW',
                'locality': 'Viman Nagar',
                'pincode': '411014',
                'can_rent': False,
                'can_borrow': True,
                'can_sell': False,
                'is_free_borrow': True,
                'borrow_security_deposit': Decimal('500.00'),
                'borrow_max_days': 4,
            },
            {
                'owner': rahul,
                'category': category_objs['Electronics'],
                'title': 'Dell UltraSharp 27-inch 4K USB-C Monitor (U2720Q)',
                'description': 'Stunning IPS 4K panel with 90W USB-C power delivery, height adjustable stand, and crisp color accuracy. Upgrading my desk setup so selling this monitor.',
                'item_condition': 'LIKE_NEW',
                'locality': 'Kothrud',
                'pincode': '411038',
                'can_rent': False,
                'can_borrow': False,
                'can_sell': True,
                'sell_price': Decimal('22500.00'),
                'sell_price_negotiable': True,
                'quantity': 1,
            },
            {
                'owner': biz_user,
                'category': category_objs['Party & Event Supplies'],
                'title': 'Epson Full HD 3500-Lumens Home Cinema Projector',
                'description': 'Ultra bright 1080p projector with HDMI, wireless projection, and portable carry case. Ideal for movie nights, cricket match screenings, and terrace gatherings.',
                'item_condition': 'GOOD',
                'locality': 'Baner',
                'pincode': '411045',
                'can_rent': True,
                'can_borrow': False,
                'can_sell': False,
                'rent_price_per_day': Decimal('850.00'),
                'rent_security_deposit': Decimal('2000.00'),
                'min_rental_days': 1,
                'max_rental_days': 5,
            },
            {
                'owner': rahul,
                'category': category_objs['Books & Study Materials'],
                'title': 'Complete UPSC / MPSC Indian Polity by M. Laxmikanth (Latest Ed)',
                'description': 'Standard reference book for civil services preparation. Unmarked pages, clean binding. Free to borrow for serious students or can be purchased permanently.',
                'item_condition': 'GOOD',
                'locality': 'Kothrud',
                'pincode': '411038',
                'can_rent': False,
                'can_borrow': True,
                'can_sell': True,
                'is_free_borrow': True,
                'borrow_security_deposit': Decimal('0.00'),
                'borrow_max_days': 21,
                'sell_price': Decimal('450.00'),
                'sell_price_negotiable': False,
                'quantity': 1,
            },
            {
                'owner': priya,
                'category': category_objs['Musical Instruments'],
                'title': 'Yamaha F310 Acoustic Guitar with Padded Gig Bag & Capo',
                'description': 'Warm tone, low action, newly restrung with D\'Addario strings. Great for acoustic practice, jamming, or learning basics. Available for rent.',
                'item_condition': 'LIKE_NEW',
                'locality': 'Viman Nagar',
                'pincode': '411014',
                'can_rent': True,
                'can_borrow': False,
                'can_sell': False,
                'rent_price_per_day': Decimal('250.00'),
                'rent_security_deposit': Decimal('1000.00'),
                'min_rental_days': 2,
                'max_rental_days': 30,
            },
            {
                'owner': biz_user,
                'category': category_objs['Sports & Fitness'],
                'title': 'Firefox Target 29T 21-Speed Mountain Bike',
                'description': 'High-performance mountain bicycle with front suspension, dual disc brakes, and Shimano tourney derailleurs. Inspected and serviced weekly.',
                'item_condition': 'GOOD',
                'locality': 'Hinjewadi',
                'pincode': '411057',
                'can_rent': True,
                'can_borrow': False,
                'can_sell': True,
                'rent_price_per_day': Decimal('350.00'),
                'rent_security_deposit': Decimal('1500.00'),
                'sell_price': Decimal('12900.00'),
                'quantity': 2,
                'min_rental_days': 1,
                'max_rental_days': 30,
            },
        ]

        for item_data in listings_data:
            listing, created = Listing.objects.get_or_create(
                owner=item_data['owner'],
                title=item_data['title'],
                defaults=item_data
            )
            if created:
                self.stdout.write(f"Created listing: {listing.title}")

        self.stdout.write(self.style.SUCCESS('Successfully seeded ShareLoop database!'))
